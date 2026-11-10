"""Substep I: independent validation of a schedule.

The solver's answer is never trusted on its own. This module re-checks it in
plain Python, starting again from the appliance settings and using the Stage 3-4
calculation engines (floating-point kW and Decimal money) instead of the
solver's integer model. It does not import OR-Tools or the model builder.

A schedule is shown as valid only if every check passes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from powershift.domain.appliance import ApplianceMode
from powershift.domain.tariff import TariffSpec
from powershift.domain.time_window import (
    MINUTES_PER_DAY,
    TIME_STEP_MINUTES,
    TimeWindow,
    format_minute,
)
from powershift.optimization.metrics import Appliances, apply_schedule, measure

COST_TOLERANCE = Decimal("0.01")
"""Per appliance: the solver stores each start's cost rounded to 1/10 000."""
PEAK_TOLERANCE_KW_PER_APPLIANCE = 0.001
"""The solver rounds each appliance's power up to a whole watt."""


@dataclass(frozen=True, slots=True)
class ScheduledRun:
    start_minute: int
    end_minute: int


@dataclass(frozen=True, slots=True)
class Check:
    code: str
    label: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ValidationReport:
    checks: tuple[Check, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


def _span(run: ScheduledRun) -> str:
    return f"{format_minute(run.start_minute)}-{format_minute(run.end_minute)}"


def validate_schedule(
    appliances: Appliances,
    schedule: Mapping[int, ScheduledRun],
    tariff: TariffSpec | None,
    limit_kw: float | None,
    reported_weekly_cost: Decimal | None,
    reported_peak_kw: float | None,
    year: int,
    month: int,
) -> ValidationReport:
    flexible = {
        i: spec for i, spec in appliances if spec.mode is ApplianceMode.FLEXIBLE and spec.flexible
    }
    names = {i: spec.name for i, spec in appliances}
    checks: list[Check] = []

    def add(code: str, label: str, problems: list[str], ok_detail: str) -> None:
        checks.append(Check(code, label, not problems, "; ".join(problems) or ok_detail))

    # 1. Exactly the flexible appliances are scheduled; fixed ones are untouched.
    problems = [f"{names[i]} has no scheduled run" for i in flexible if i not in schedule]
    problems += [
        f"{names.get(i, f'appliance {i}')} is not a flexible appliance but was scheduled"
        for i in schedule
        if i not in flexible
    ]
    add(
        "assignment",
        "Every flexible appliance scheduled once; fixed appliances untouched",
        problems,
        f"{len(flexible)} flexible appliance(s) scheduled",
    )

    runs = {i: run for i, run in schedule.items() if i in flexible}

    # 2. Times are real times on the 15-minute grid.
    problems = [
        f"{names[i]} has an invalid time {_span(run)}"
        for i, run in runs.items()
        if not (0 <= run.start_minute < MINUTES_PER_DAY and 0 < run.end_minute <= MINUTES_PER_DAY)
        or run.start_minute % TIME_STEP_MINUTES
        or run.end_minute % TIME_STEP_MINUTES
    ]
    add("time_grid", "Start and end times lie on the 15-minute grid", problems, "All times valid")
    if problems:
        return ValidationReport(tuple(checks))  # later checks need valid times

    # 3. Required duration, as one uninterrupted block.
    problems = []
    for i, run in runs.items():
        needed = flexible[i].flexible.run_duration_minutes  # type: ignore[union-attr]
        actual = TimeWindow(run.start_minute, run.end_minute).length_minutes
        if actual != needed:
            problems.append(f"{names[i]} runs {actual} min instead of {needed} min")
    add(
        "duration",
        "Each run is one uninterrupted block of the required duration",
        problems,
        "All durations match",
    )

    # 4. Operating windows.
    problems = []
    for i, run in runs.items():
        flex = flexible[i].flexible
        assert flex is not None
        if not flex.allowed_window.fits(run.start_minute, flex.run_duration_minutes):
            allowed = flex.allowed_window
            problems.append(
                f"{names[i]} at {_span(run)} is outside its window "
                f"{format_minute(allowed.start_minute)}-{format_minute(allowed.end_minute)}"
            )
    add(
        "window", "Each run is inside its allowed window", problems, "All runs inside their windows"
    )

    # 5-7 use the calculation engines on the rescheduled household.
    moved = apply_schedule(appliances, {i: run.start_minute for i, run in runs.items()})
    metrics = measure(moved, tariff, limit_kw, year, month)

    if limit_kw is None:
        checks.append(
            Check("load_limit", "Household load limit respected", True, "No load limit is set")
        )
    else:
        add(
            "load_limit",
            "Household load limit respected",
            [
                f"{metrics.minutes_over_limit} min per week above {limit_kw:g} kW "
                f"(peak {metrics.peak_kw:.3f} kW)"
            ]
            if metrics.minutes_over_limit
            else [],
            f"Peak {metrics.peak_kw:.3f} kW is within the {limit_kw:g} kW limit",
        )

    add(
        "not_simultaneous",
        "Appliances marked 'not simultaneous' never overlap",
        [f"{metrics.conflict_minutes} min per week of overlap"] if metrics.conflict_minutes else [],
        "No overlaps",
    )

    # 7. The numbers the solver reported match an independent recalculation.
    problems = []
    if reported_peak_kw is not None:
        tolerance = PEAK_TOLERANCE_KW_PER_APPLIANCE * (len(appliances) + 1)
        if abs(reported_peak_kw - metrics.peak_kw) > tolerance:
            problems.append(
                f"peak: solver {reported_peak_kw:.3f} kW vs recalculated {metrics.peak_kw:.3f} kW"
            )
    if reported_weekly_cost is not None and metrics.weekly_energy_charge is not None:
        tolerance_cost = COST_TOLERANCE * (len(flexible) + 1)
        # The solver only prices flexible appliances; add the fixed ones' share.
        fixed_only = [(i, s) for i, s in appliances if s.mode is ApplianceMode.FIXED]
        fixed_cost = measure(fixed_only, tariff, None, year, month).weekly_energy_charge or Decimal(
            0
        )
        expected = metrics.weekly_energy_charge - fixed_cost
        if abs(reported_weekly_cost - expected) > tolerance_cost:
            problems.append(
                f"cost: solver {reported_weekly_cost:.4f} vs recalculated {expected:.4f} per week"
            )
    add(
        "objective",
        "Solver's cost and peak match an independent recalculation",
        problems,
        "Cost and peak agree",
    )

    return ValidationReport(tuple(checks))
