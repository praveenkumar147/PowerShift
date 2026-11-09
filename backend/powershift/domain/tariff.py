"""Electricity tariff model and consistency rules.

Supported structures (all rates are user-entered; nothing is hard-coded):

- FLAT:  one price per kWh, all day, every day.
- TOU:   time-of-use. Price depends on the time of day, optionally different on
         weekdays (Mon-Fri) and weekends (Sat-Sun). Periods must cover every
         minute of each day exactly once.
- SLAB:  price depends on how much is used in the billing month. Slabs are
         consumption bands, e.g. 0-100 kWh, 100-200 kWh, 200+ kWh.

Plus charges added after the energy charge:
- FIXED_MONTHLY: a fixed amount per month (e.g. meter rent).
- PER_KWH:       an extra amount per kWh (e.g. fuel surcharge).
- PERCENTAGE:    a percentage of the subtotal (e.g. electricity duty / tax).

Money uses Decimal, never float, so 0.1 + 0.2 is exactly 0.3.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from powershift.domain.time_window import (
    STEPS_PER_DAY,
    TIME_STEP_MINUTES,
    TimeWindow,
    format_minute,
)

WEEKEND_DAYS = frozenset({5, 6})  # Saturday, Sunday (0 = Monday)


class TariffType(StrEnum):
    FLAT = "flat"
    TOU = "tou"
    SLAB = "slab"


class DayType(StrEnum):
    ALL = "all"
    WEEKDAY = "weekday"
    WEEKEND = "weekend"

    def applies_to(self, weekday: int) -> bool:
        if self is DayType.ALL:
            return True
        is_weekend = weekday in WEEKEND_DAYS
        return is_weekend if self is DayType.WEEKEND else not is_weekend


class SlabMode(StrEnum):
    TELESCOPIC = "telescopic"
    """Each band's kWh are charged at that band's rate (most common)."""
    WHOLE_USAGE = "whole_usage"
    """All kWh are charged at the rate of the highest band reached."""


class ChargeKind(StrEnum):
    FIXED_MONTHLY = "fixed_monthly"
    PER_KWH = "per_kwh"
    PERCENTAGE = "percentage"


@dataclass(frozen=True, slots=True)
class TouPeriod:
    window: TimeWindow
    day_type: DayType
    rate_per_kwh: Decimal


@dataclass(frozen=True, slots=True)
class Slab:
    up_to_kwh: Decimal | None
    """Upper limit of this band (monthly kWh); None = no limit (the last band)."""
    rate_per_kwh: Decimal


@dataclass(frozen=True, slots=True)
class Charge:
    kind: ChargeKind
    label: str
    amount: Decimal
    """Currency per month, currency per kWh, or percent (0-100), depending on kind."""


@dataclass(frozen=True, slots=True)
class TariffSpec:
    name: str
    tariff_type: TariffType
    effective_date: date
    flat_rate_per_kwh: Decimal | None
    tou_periods: tuple[TouPeriod, ...]
    slabs: tuple[Slab, ...]
    slab_mode: SlabMode
    charges: tuple[Charge, ...]


def validate_tariff(spec: TariffSpec) -> dict[str, str]:
    """Returns {field path: message}; empty when the tariff is consistent."""
    errors: dict[str, str] = {}
    is_type = spec.tariff_type

    if is_type is TariffType.FLAT and spec.flat_rate_per_kwh is None:
        errors["flat_rate_per_kwh"] = "Enter the price per kWh."
    if is_type is not TariffType.FLAT and spec.flat_rate_per_kwh is not None:
        errors["flat_rate_per_kwh"] = "Only flat tariffs have a single price."

    if is_type is TariffType.TOU:
        errors.update(_validate_tou(spec.tou_periods))
    elif spec.tou_periods:
        errors["tou_periods"] = "Only time-of-use tariffs have time periods."

    if is_type is TariffType.SLAB:
        errors.update(_validate_slabs(spec.slabs))
    elif spec.slabs:
        errors["slabs"] = "Only slab tariffs have consumption slabs."

    return errors


def _validate_tou(periods: tuple[TouPeriod, ...]) -> dict[str, str]:
    if not periods:
        return {"tou_periods": "Add at least one time period."}
    day_types = {p.day_type for p in periods}
    if DayType.ALL in day_types and len(day_types) > 1:
        return {
            "tou_periods": "Use either 'every day' periods, or separate weekday and weekend "
            "periods, not both."
        }
    groups = [DayType.ALL] if DayType.ALL in day_types else [DayType.WEEKDAY, DayType.WEEKEND]
    for group in groups:
        problem = _coverage_problem([p.window for p in periods if p.day_type is group])
        if problem:
            label = {
                DayType.ALL: "",
                DayType.WEEKDAY: " on weekdays",
                DayType.WEEKEND: " on weekends",
            }
            return {"tou_periods": f"{problem}{label[group]}."}
    return {}


def _coverage_problem(windows: list[TimeWindow]) -> str | None:
    """Every 15-minute step of the day must be covered exactly once."""
    counts = [0] * STEPS_PER_DAY
    for window in windows:
        for step in window.steps():
            counts[step] += 1
    for step, count in enumerate(counts):
        time = format_minute(step * TIME_STEP_MINUTES)
        if count == 0:
            return (
                f"No price is set for {time}" if windows else "Add periods covering the whole day"
            )
        if count > 1:
            return f"Periods overlap at {time}"
    return None


def _validate_slabs(slabs: tuple[Slab, ...]) -> dict[str, str]:
    if not slabs:
        return {"slabs": "Add at least one slab."}
    previous = Decimal(0)
    for index, slab in enumerate(slabs):
        is_last = index == len(slabs) - 1
        if slab.up_to_kwh is None and not is_last:
            return {f"slabs.{index}.up_to_kwh": "Only the last slab can have no upper limit."}
        if slab.up_to_kwh is None:
            continue
        if is_last:
            return {f"slabs.{index}.up_to_kwh": "Leave the last slab's upper limit empty."}
        if slab.up_to_kwh <= previous:
            return {
                f"slabs.{index}.up_to_kwh": "Each upper limit must be higher than the previous one."
            }
        previous = slab.up_to_kwh
    return {}
