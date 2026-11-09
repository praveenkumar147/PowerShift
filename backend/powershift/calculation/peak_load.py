"""Peak load analysis: household POWER demand (kW) through a typical day.

kW vs kWh: energy (kWh) is what you pay for; demand (kW) is how hard the
connection is being pushed at one moment. A breaker or a sanctioned-load limit
is about demand, so this module only ever works in kW.

Two demand figures for every 15-minute step:
- worst case : every appliance that is ON draws its full rated power at once.
               Cycling appliances (fridge, AC) can line up, so load-limit
               warnings use this figure.
- expected   : rated power x duty cycle; the typical average.

15-minute steps are used (not hours) because a short spike inside an hour
would otherwise be averaged away.

Definitions (constants below, so they are stated once and tested):
- High-demand period : worst-case demand >= 80% of the load limit
                       (or of the day's own peak when no limit is set).
- Heavy appliance     : full power >= 1 kW. Two or more heavy appliances on at
                       the same time is reported as an overlap.
- Conflict            : two or more appliances marked "not simultaneous" are on
                       at the same time in the current schedule.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from powershift.calculation.appliance_energy import average_power_kw, max_power_kw
from powershift.calculation.load_profile import WEEKDAYS, on_steps
from powershift.domain.appliance import ApplianceCategory, ApplianceMode, ApplianceSpec
from powershift.domain.time_window import MINUTES_PER_DAY, STEPS_PER_DAY, TIME_STEP_MINUTES

HIGH_DEMAND_FRACTION = 0.8
HEAVY_APPLIANCE_KW = 1.0
EPSILON_KW = 1e-9
"""Tolerance for float comparisons: demand exactly AT the limit is not a violation."""


@dataclass(frozen=True, slots=True)
class ApplianceDemand:
    appliance_id: int
    name: str
    category: ApplianceCategory
    mode: ApplianceMode
    max_kw: float
    average_kw: float
    allow_simultaneous: bool
    on_steps: frozenset[int]
    operating_days: frozenset[int]

    def is_on(self, weekday: int, step: int) -> bool:
        return weekday in self.operating_days and step in self.on_steps

    @property
    def is_heavy(self) -> bool:
        return self.max_kw >= HEAVY_APPLIANCE_KW


def build_demands(appliances: Sequence[tuple[int, ApplianceSpec]]) -> list[ApplianceDemand]:
    return [
        ApplianceDemand(
            appliance_id=appliance_id,
            name=spec.name,
            category=spec.category,
            mode=spec.mode,
            max_kw=max_power_kw(spec),
            average_kw=average_power_kw(spec),
            allow_simultaneous=spec.allow_simultaneous,
            on_steps=frozenset(on_steps(spec)),
            operating_days=frozenset(spec.operating_days),
        )
        for appliance_id, spec in appliances
    ]


@dataclass(frozen=True, slots=True)
class Step:
    index: int
    worst_kw: float
    expected_kw: float
    fixed_kw: float
    """Worst-case demand from fixed (baseline) appliances."""
    flexible_kw: float
    """Worst-case demand from flexible appliances."""
    running: tuple[ApplianceDemand, ...]
    """Appliances on in this step, highest full power first."""

    @property
    def start_minute(self) -> int:
        return self.index * TIME_STEP_MINUTES


@dataclass(frozen=True, slots=True)
class Window:
    """A run of consecutive steps; may wrap past midnight (end <= start)."""

    first_step: int
    step_count: int

    @property
    def start_minute(self) -> int:
        return self.first_step * TIME_STEP_MINUTES

    @property
    def end_minute(self) -> int:
        end = (self.start_minute + self.step_count * TIME_STEP_MINUTES) % MINUTES_PER_DAY
        return end or MINUTES_PER_DAY

    @property
    def minutes(self) -> int:
        return self.step_count * TIME_STEP_MINUTES

    def step_indexes(self) -> list[int]:
        return [(self.first_step + i) % STEPS_PER_DAY for i in range(self.step_count)]


@dataclass(frozen=True, slots=True)
class Episode:
    """A window together with the appliances involved and its highest demand."""

    window: Window
    max_kw: float
    appliances: tuple[ApplianceDemand, ...]


@dataclass(frozen=True, slots=True)
class DayAnalysis:
    weekday: int
    load_limit_kw: float | None
    steps: tuple[Step, ...]
    peak_kw: float
    peak_expected_kw: float
    peak_windows: tuple[Window, ...]
    peak_step: Step
    """The first step at the peak; its appliances are the peak contributors."""
    violations: tuple[Episode, ...]
    high_demand: tuple[Episode, ...]
    overlaps: tuple[Episode, ...]
    conflicts: tuple[Episode, ...]

    @property
    def minutes_over_limit(self) -> int:
        return sum(v.window.minutes for v in self.violations)


@dataclass(frozen=True, slots=True)
class DaySummary:
    weekday: int
    peak_kw: float
    peak_expected_kw: float
    peak_start_minute: int
    minutes_over_limit: int


def day_steps(demands: Sequence[ApplianceDemand], weekday: int) -> list[Step]:
    steps = []
    for index in range(STEPS_PER_DAY):
        running = tuple(
            sorted(
                (d for d in demands if d.is_on(weekday, index)),
                key=lambda d: (-d.max_kw, d.name.lower()),
            )
        )
        fixed = sum(d.max_kw for d in running if d.mode is ApplianceMode.FIXED)
        flexible = sum(d.max_kw for d in running if d.mode is ApplianceMode.FLEXIBLE)
        steps.append(
            Step(
                index=index,
                worst_kw=fixed + flexible,
                expected_kw=sum(d.average_kw for d in running),
                fixed_kw=fixed,
                flexible_kw=flexible,
                running=running,
            )
        )
    return steps


def find_windows(flags: Sequence[bool]) -> list[Window]:
    """Runs of True in a cyclic day. A run touching both midnight ends is one window."""
    n = len(flags)
    if all(flags):
        return [Window(0, n)]
    windows: list[Window] = []
    index = 0
    while index < n:
        if flags[index]:
            start = index
            while index < n and flags[index]:
                index += 1
            windows.append(Window(start, index - start))
        else:
            index += 1
    # Merge "23:30-24:00" with "00:00-01:00" into "23:30-01:00".
    if len(windows) > 1 and windows[0].first_step == 0 and flags[n - 1]:
        first, last = windows[0], windows[-1]
        windows = [Window(last.first_step, last.step_count + first.step_count), *windows[1:-1]]
    return sorted(windows, key=lambda w: w.first_step)


def _episodes(
    steps: Sequence[Step],
    condition: Callable[[Step], bool],
    involved: Callable[[Step], Sequence[ApplianceDemand]],
    magnitude: Callable[[Step], float],
) -> tuple[Episode, ...]:
    episodes = []
    for window in find_windows([condition(step) for step in steps]):
        window_steps = [steps[i] for i in window.step_indexes()]
        members: dict[int, ApplianceDemand] = {}
        for step in window_steps:
            for demand in involved(step):
                members.setdefault(demand.appliance_id, demand)
        episodes.append(
            Episode(
                window=window,
                max_kw=max(magnitude(step) for step in window_steps),
                appliances=tuple(
                    sorted(members.values(), key=lambda d: (-d.max_kw, d.name.lower()))
                ),
            )
        )
    return tuple(episodes)


def analyse_day(
    demands: Sequence[ApplianceDemand], weekday: int, load_limit_kw: float | None
) -> DayAnalysis:
    steps = day_steps(demands, weekday)
    peak = max(step.worst_kw for step in steps)
    at_peak = [peak > EPSILON_KW and abs(step.worst_kw - peak) <= EPSILON_KW for step in steps]
    peak_windows = find_windows(at_peak) if any(at_peak) else []
    peak_step = steps[peak_windows[0].first_step] if peak_windows else steps[0]

    threshold_base = load_limit_kw if load_limit_kw is not None else peak
    high_threshold = threshold_base * HIGH_DEMAND_FRACTION

    def running(step: Step) -> Sequence[ApplianceDemand]:
        return step.running

    def total_kw(step: Step) -> float:
        return step.worst_kw

    def heavy(step: Step) -> list[ApplianceDemand]:
        return [d for d in step.running if d.is_heavy]

    def heavy_kw(step: Step) -> float:
        return sum(d.max_kw for d in heavy(step))

    def exclusive(step: Step) -> list[ApplianceDemand]:
        return [d for d in step.running if not d.allow_simultaneous]

    def exclusive_kw(step: Step) -> float:
        return sum(d.max_kw for d in exclusive(step))

    limit = load_limit_kw
    violations = (
        _episodes(steps, lambda s: s.worst_kw > limit + EPSILON_KW, running, total_kw)
        if limit is not None
        else ()
    )

    return DayAnalysis(
        weekday=weekday,
        load_limit_kw=load_limit_kw,
        steps=tuple(steps),
        peak_kw=peak,
        peak_expected_kw=max(step.expected_kw for step in steps),
        peak_windows=tuple(peak_windows),
        peak_step=peak_step,
        violations=violations,
        high_demand=_episodes(
            steps,
            lambda s: peak > EPSILON_KW and s.worst_kw >= high_threshold - EPSILON_KW,
            running,
            total_kw,
        ),
        overlaps=_episodes(steps, lambda s: len(heavy(s)) >= 2, heavy, heavy_kw),
        conflicts=_episodes(steps, lambda s: len(exclusive(s)) >= 2, exclusive, exclusive_kw),
    )


def summarise_week(
    demands: Sequence[ApplianceDemand], load_limit_kw: float | None
) -> list[DaySummary]:
    summaries = []
    for weekday in WEEKDAYS:
        day = analyse_day(demands, weekday, load_limit_kw)
        summaries.append(
            DaySummary(
                weekday=weekday,
                peak_kw=day.peak_kw,
                peak_expected_kw=day.peak_expected_kw,
                peak_start_minute=day.peak_step.start_minute,
                minutes_over_limit=day.minutes_over_limit,
            )
        )
    return summaries


def worst_weekday(summaries: Sequence[DaySummary]) -> int:
    """Day with the highest worst-case peak.

    Ties go to the day with more time over the limit, then to the earliest day.
    """
    return max(summaries, key=lambda s: (s.peak_kw, s.minutes_over_limit, -s.weekday)).weekday
