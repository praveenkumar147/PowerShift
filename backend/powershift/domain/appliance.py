"""Appliance domain model and consistency rules.

Pure Python: no database, no HTTP. The API layer checks field types and ranges;
this module checks rules that involve several fields together, such as
"the run must fit inside the allowed window".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from powershift.domain.time_window import TimeWindow, format_minute, windows_overlap


class ApplianceCategory(StrEnum):
    COOLING = "cooling"
    LIGHTING = "lighting"
    KITCHEN = "kitchen"
    LAUNDRY = "laundry"
    ENTERTAINMENT = "entertainment"
    WATER_HEATING = "water_heating"
    ELECTRONICS = "electronics"
    OTHER = "other"


class ApplianceMode(StrEnum):
    FIXED = "fixed"
    """Runs at set times (fridge, router, lights). Forms the baseline load."""
    FLEXIBLE = "flexible"
    """Run time can move (washing machine, dishwasher). The optimizer may reschedule it."""


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class FlexibleSchedule:
    run_duration_minutes: int
    """Time the appliance needs per run (e.g. 90 for a wash cycle)."""
    allowed_window: TimeWindow
    """Hard limit: the whole run must happen inside this window."""
    current_start_minute: int
    """When the household usually starts it today. This is the baseline for savings."""
    preferred_window: TimeWindow | None
    """Soft preference inside the allowed window (used by the scheduler in Stage 5)."""
    must_be_contiguous: bool


@dataclass(frozen=True, slots=True)
class ApplianceSpec:
    """Everything the user configures about one appliance."""

    name: str
    category: ApplianceCategory
    rated_power_w: float
    """Nameplate power of ONE unit while running at full power."""
    quantity: int
    duty_cycle: float
    """Fraction (0-1] of on-time actually drawing rated power. A fridge compressor ~0.4."""
    mode: ApplianceMode
    priority: Priority
    allow_simultaneous: bool
    """False: must not run at the same time as other appliances that are also False."""
    operating_days: tuple[int, ...]
    """Weekdays it is used: 0 = Monday ... 6 = Sunday."""
    fixed_blocks: tuple[TimeWindow, ...]
    flexible: FlexibleSchedule | None


def validate_appliance(spec: ApplianceSpec) -> dict[str, str]:
    """Returns {field path: message} for every broken rule; empty when consistent.

    Field paths match the API request fields so the UI can show each message
    next to the right input.
    """
    errors: dict[str, str] = {}

    if spec.mode is ApplianceMode.FIXED:
        if spec.flexible is not None:
            errors["flexible"] = "Fixed appliances cannot have flexible scheduling settings."
        if not spec.fixed_blocks:
            errors["fixed_blocks"] = "Add at least one time period when the appliance is on."
        elif windows_overlap(spec.fixed_blocks):
            errors["fixed_blocks"] = "Time periods overlap; each minute may be counted only once."
    else:
        if spec.fixed_blocks:
            errors["fixed_blocks"] = (
                "Flexible appliances are scheduled by run time, not fixed periods."
            )
        if spec.flexible is None:
            errors["flexible"] = "Flexible appliances need a run duration and allowed window."
        else:
            errors.update(_validate_flexible(spec.flexible))

    return errors


def _validate_flexible(flex: FlexibleSchedule) -> dict[str, str]:
    errors: dict[str, str] = {}
    window = flex.allowed_window
    duration = flex.run_duration_minutes

    if duration > window.length_minutes:
        errors["flexible.run_duration_minutes"] = (
            f"A {duration}-minute run cannot fit in the allowed window "
            f"{format_minute(window.start_minute)}-{format_minute(window.end_minute)} "
            f"({window.length_minutes} minutes)."
        )
        return errors  # the remaining checks depend on the run fitting at all

    if not window.fits(flex.current_start_minute, duration):
        errors["flexible.current_start_minute"] = (
            "Starting at this time, the run would not finish inside the allowed window."
        )

    preferred = flex.preferred_window
    if preferred is not None:
        if not window.contains_window(preferred):
            errors["flexible.preferred_window"] = (
                "The preferred window must lie inside the allowed window."
            )
        elif duration > preferred.length_minutes:
            errors["flexible.preferred_window"] = (
                "The preferred window is shorter than the run duration."
            )

    return errors
