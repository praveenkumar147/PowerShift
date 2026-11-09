"""Typical-day load profiles.

For each appliance and each weekday we build 96 values: the estimated AVERAGE
power (kW) in each 15-minute step of the day. Energy in a step is then

    energy (kWh) = average power (kW) x 0.25 h

Model assumptions (documented for the user):
- A "day" is a typical day for that weekday. A period that runs past midnight
  (22:00-02:00) is counted within the same day's 24 hours (a cyclic day), which
  gives correct daily totals for a repeating routine.
- Flexible appliances run at their CURRENT usual start time. This is the
  baseline the optimizer will later compare against.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from powershift.calculation.appliance_energy import average_power_kw
from powershift.domain.appliance import ApplianceCategory, ApplianceMode, ApplianceSpec
from powershift.domain.time_window import STEPS_PER_DAY, TIME_STEP_MINUTES, run_window

STEP_HOURS = TIME_STEP_MINUTES / 60
WEEKDAYS = range(7)

DayProfile = tuple[float, ...]
"""96 average-kW values, one per 15-minute step."""


@dataclass(frozen=True, slots=True)
class ApplianceLoad:
    appliance_id: int
    name: str
    category: ApplianceCategory
    mode: ApplianceMode
    profiles: tuple[DayProfile, ...]
    """One DayProfile per weekday, index 0 = Monday."""

    def day_kwh(self, weekday: int) -> float:
        return sum(self.profiles[weekday]) * STEP_HOURS


def on_steps(spec: ApplianceSpec) -> set[int]:
    """The 15-minute steps of a day in which the appliance is switched on."""
    if spec.mode is ApplianceMode.FIXED:
        return {step for block in spec.fixed_blocks for step in block.steps()}
    if spec.flexible is None:
        return set()
    flex = spec.flexible
    return set(run_window(flex.current_start_minute, flex.run_duration_minutes).steps())


def build_load(appliance_id: int, spec: ApplianceSpec) -> ApplianceLoad:
    steps = on_steps(spec)
    kw = average_power_kw(spec)
    active_day = tuple(kw if step in steps else 0.0 for step in range(STEPS_PER_DAY))
    idle_day = (0.0,) * STEPS_PER_DAY
    return ApplianceLoad(
        appliance_id=appliance_id,
        name=spec.name,
        category=spec.category,
        mode=spec.mode,
        profiles=tuple(
            active_day if weekday in spec.operating_days else idle_day for weekday in WEEKDAYS
        ),
    )


def build_loads(appliances: Sequence[tuple[int, ApplianceSpec]]) -> list[ApplianceLoad]:
    return [build_load(appliance_id, spec) for appliance_id, spec in appliances]
