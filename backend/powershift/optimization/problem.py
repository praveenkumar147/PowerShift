"""Substep A: the scheduling problem the solver receives.

Plain-language model
--------------------
For every flexible appliance, choose ONE start time (used on every day it runs) so
that:
  - the whole run fits inside its allowed window,
  - the household never exceeds its load limit (worst case, every 15 minutes, every weekday),
  - appliances marked "not simultaneous" never overlap,
and the chosen goal (lowest cost, lowest peak, or a balance) is as good as possible.

Fixed appliances are NOT decisions: they form the baseline load `base_w`.

Units inside the solver are integers (CP-SAT only works with integers):
  power  -> whole watts, rounded UP for appliances and DOWN for the limit, so a
            schedule the solver accepts is truly within the limit;
  money  -> units of 1/10 000 of the currency (COST_SCALE).

Time
----
- Demand and cost are evaluated at 15-minute steps (96 per day), exactly.
- Candidate start times lie on a grid of `start_step_minutes` (60 by default:
  "hourly slots"; 30 and 15 are supported). The appliance's CURRENT start is
  always added as a candidate, so if today's schedule is valid the solver can
  never return something worse than it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from powershift.calculation.appliance_energy import average_power_kw, max_power_kw
from powershift.calculation.load_profile import STEP_HOURS, WEEKDAYS, on_steps
from powershift.calculation.tariff_engine import step_prices
from powershift.domain.appliance import ApplianceMode, ApplianceSpec
from powershift.domain.tariff import TariffSpec, TariffType
from powershift.domain.time_window import (
    MINUTES_PER_DAY,
    STEPS_PER_DAY,
    TIME_STEP_MINUTES,
    TimeWindow,
    run_window,
)

COST_SCALE = 10_000
"""Integer cost units per 1 unit of currency."""
WATTS_PER_KW = 1000
ALLOWED_START_STEPS = (15, 30, 60)


class Priority(StrEnum):
    COST = "cost"
    PEAK = "peak"
    BALANCED = "balanced"


@dataclass(frozen=True, slots=True)
class Task:
    """One flexible appliance to schedule."""

    appliance_id: int
    name: str
    power_w: int
    """Full power (rated x quantity), rounded UP to whole watts."""
    average_kw: float
    duration_minutes: int
    window: TimeWindow
    current_start_minute: int
    preferred_window: TimeWindow | None
    days: tuple[int, ...]
    allow_simultaneous: bool
    candidates: tuple[int, ...]
    """Allowed start minutes: grid points whose whole run fits the window, plus the usual start."""
    cost_by_start: dict[int, int] = field(default_factory=dict)
    """Weekly energy charge (COST_SCALE units) of starting at each candidate."""

    @property
    def step_count(self) -> int:
        return self.duration_minutes // TIME_STEP_MINUTES

    def steps_for(self, start_minute: int) -> list[int]:
        return run_window(start_minute, self.duration_minutes).steps()

    def in_preferred_window(self, start_minute: int) -> bool:
        return self.preferred_window is None or self.preferred_window.fits(
            start_minute, self.duration_minutes
        )

    def displacement(self, start_minute: int) -> int:
        """Minutes between a start and the usual start, the short way round the clock."""
        diff = abs(start_minute - self.current_start_minute) % MINUTES_PER_DAY
        return min(diff, MINUTES_PER_DAY - diff)


@dataclass(frozen=True, slots=True)
class SchedulingProblem:
    tasks: tuple[Task, ...]
    base_w: tuple[tuple[int, ...], ...]
    """Fixed-appliance worst-case load in W, [weekday][step]."""
    limit_w: int | None
    tariff_type: TariffType | None
    start_step_minutes: int

    @property
    def cost_is_time_dependent(self) -> bool:
        """Only time-of-use prices change with the time of day."""
        return self.tariff_type is TariffType.TOU


@dataclass(frozen=True, slots=True)
class InputIssue:
    """A reason the problem cannot be solved as configured, found before solving."""

    code: str
    message: str
    appliance_id: int | None = None


def candidate_starts(
    window: TimeWindow, duration: int, current: int, step_minutes: int
) -> tuple[int, ...]:
    grid = range(0, MINUTES_PER_DAY, step_minutes)
    starts = {s for s in grid if window.fits(s, duration)}
    if window.fits(current, duration):
        starts.add(current)
    return tuple(sorted(starts))


def _weekly_cost(
    task_kw: float,
    days: Sequence[int],
    steps: Sequence[int],
    prices: Sequence[tuple[Decimal, ...] | None],
) -> int:
    total = Decimal(0)
    kwh_per_step = Decimal(repr(task_kw * STEP_HOURS))
    for weekday in days:
        day_prices = prices[weekday]
        if day_prices is None:
            continue
        total += sum((day_prices[s] * kwh_per_step for s in steps), Decimal(0))
    return int((total * COST_SCALE).to_integral_value())


def build_problem(
    appliances: Sequence[tuple[int, ApplianceSpec]],
    tariff: TariffSpec | None,
    limit_kw: float | None,
    start_step_minutes: int = 60,
) -> SchedulingProblem:
    if start_step_minutes not in ALLOWED_START_STEPS:
        raise ValueError(f"start_step_minutes must be one of {ALLOWED_START_STEPS}")

    prices = [step_prices(tariff, w) if tariff else None for w in WEEKDAYS]
    base = [[0] * STEPS_PER_DAY for _ in WEEKDAYS]
    tasks: list[Task] = []

    for appliance_id, spec in appliances:
        power_w = math.ceil(max_power_kw(spec) * WATTS_PER_KW - 1e-9)
        if spec.mode is ApplianceMode.FIXED:
            steps = on_steps(spec)
            for weekday in spec.operating_days:
                for step in steps:
                    base[weekday][step] += power_w
            continue
        flex = spec.flexible
        if flex is None:  # prevented by appliance validation; skip defensively
            continue
        candidates = candidate_starts(
            flex.allowed_window,
            flex.run_duration_minutes,
            flex.current_start_minute,
            start_step_minutes,
        )
        days = tuple(sorted(spec.operating_days))
        avg_kw = average_power_kw(spec)
        tasks.append(
            Task(
                appliance_id=appliance_id,
                name=spec.name,
                power_w=power_w,
                average_kw=avg_kw,
                duration_minutes=flex.run_duration_minutes,
                window=flex.allowed_window,
                current_start_minute=flex.current_start_minute,
                preferred_window=flex.preferred_window,
                days=days,
                allow_simultaneous=spec.allow_simultaneous,
                candidates=candidates,
                cost_by_start={
                    start: _weekly_cost(
                        avg_kw, days, run_window(start, flex.run_duration_minutes).steps(), prices
                    )
                    for start in candidates
                },
            )
        )

    return SchedulingProblem(
        tasks=tuple(tasks),
        base_w=tuple(tuple(day) for day in base),
        limit_w=math.floor(limit_kw * WATTS_PER_KW + 1e-9) if limit_kw is not None else None,
        tariff_type=tariff.tariff_type if tariff else None,
        start_step_minutes=start_step_minutes,
    )


def validate_problem(problem: SchedulingProblem, priority: Priority) -> list[InputIssue]:
    """Checks that make solving pointless or impossible, with plain explanations."""
    issues: list[InputIssue] = []
    if not problem.tasks:
        issues.append(
            InputIssue("no_flexible_appliances", "There are no flexible appliances to schedule.")
        )
    if priority in (Priority.COST, Priority.BALANCED) and problem.tariff_type is None:
        issues.append(
            InputIssue(
                "no_tariff",
                "Cost can't be optimised without an active tariff. "
                "Add a tariff, or choose 'Lowest peak demand'.",
            )
        )
    for task in problem.tasks:
        if not task.candidates:
            issues.append(
                InputIssue(
                    "no_start_fits",
                    f"{task.name}: no start time on the {problem.start_step_minutes}-minute grid "
                    f"lets the {task.duration_minutes}-minute run fit its window. "
                    "Use a finer start-time step or widen the window.",
                    task.appliance_id,
                )
            )
    return issues


@dataclass(frozen=True, slots=True)
class Evaluation:
    """The integer model's view of one complete schedule (plain Python, no solver)."""

    cost: int
    peak_w: int
    preferred_misses: int
    movement_minutes: int
    within_limit: bool
    no_conflicts: bool

    @property
    def feasible(self) -> bool:
        return self.within_limit and self.no_conflicts


def evaluate(problem: SchedulingProblem, starts: dict[int, int]) -> Evaluation:
    """Scores a schedule {appliance_id: start minute} exactly as the model defines it.

    Used for the baseline reference values and, in tests, to brute-force the true
    optimum and compare it with the solver's answer.
    """
    load = [list(day) for day in problem.base_w]
    exclusive = [[0] * STEPS_PER_DAY for _ in WEEKDAYS]
    cost = misses = movement = 0
    for task in problem.tasks:
        start = starts[task.appliance_id]
        cost += task.cost_by_start[start]
        misses += 0 if task.in_preferred_window(start) else 1
        movement += task.displacement(start)
        for step in task.steps_for(start):
            for weekday in task.days:
                load[weekday][step] += task.power_w
                if not task.allow_simultaneous:
                    exclusive[weekday][step] += 1
    peak = max(max(day) for day in load)
    return Evaluation(
        cost=cost,
        peak_w=peak,
        preferred_misses=misses,
        movement_minutes=movement,
        within_limit=problem.limit_w is None or peak <= problem.limit_w,
        no_conflicts=all(count <= 1 for day in exclusive for count in day),
    )


def baseline_starts(problem: SchedulingProblem) -> dict[int, int]:
    """The household's current schedule: every appliance at its usual start."""
    return {task.appliance_id: task.current_start_minute for task in problem.tasks}
