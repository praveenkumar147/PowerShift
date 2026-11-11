"""Cost and peak figures for a schedule, computed by the normal calculation
engines (Stage 3 energy model, Stage 4 peak analysis), not by the solver.

The same function measures the current schedule and the optimised one, so
"before" and "after" are always compared like for like.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from powershift.calculation.energy_model import EnergyModel
from powershift.calculation.load_profile import WEEKDAYS, build_loads
from powershift.calculation.peak_load import DayAnalysis, analyse_day, build_demands
from powershift.domain.appliance import ApplianceSpec
from powershift.domain.tariff import TariffSpec, TariffType

REFERENCE_MONDAY = date(2024, 1, 1)
"""Any Monday: one Monday-to-Sunday week contains each weekday exactly once."""

Appliances = Sequence[tuple[int, ApplianceSpec]]


def apply_schedule(
    appliances: Appliances, starts: Mapping[int, int]
) -> list[tuple[int, ApplianceSpec]]:
    """The household with flexible appliances moved to the given start minutes."""
    moved = []
    for appliance_id, spec in appliances:
        if appliance_id in starts and spec.flexible is not None:
            flexible = replace(spec.flexible, current_start_minute=starts[appliance_id])
            spec = replace(spec, flexible=flexible)
        moved.append((appliance_id, spec))
    return moved


@dataclass(frozen=True, slots=True)
class ScheduleMetrics:
    monthly_kwh: float
    """Estimated energy for the reference month."""
    weekly_energy_charge: Decimal | None
    """Energy charge for one typical week; None unless the tariff is flat or time-of-use."""
    monthly_bill: Decimal | None
    """Full estimated bill for the reference month; None without a tariff."""
    peak_kw: float
    """Highest worst-case demand in the week."""
    peak_expected_kw: float
    peak_weekday: int
    minutes_over_limit: int
    """Per week."""
    conflict_minutes: int
    """Per week: time that appliances marked "not simultaneous" overlap."""
    days: tuple[DayAnalysis, ...]


def measure(
    appliances: Appliances, tariff: TariffSpec | None, limit_kw: float | None, year: int, month: int
) -> ScheduleMetrics:
    model = EnergyModel(build_loads(appliances), tariff)
    weekly = None
    if tariff is not None and tariff.tariff_type is not TariffType.SLAB:
        weekly = model.period_report(
            REFERENCE_MONDAY, REFERENCE_MONDAY + timedelta(days=6)
        ).energy_charge
    bill = model.month_bill(year, month)

    demands = build_demands(appliances)
    days = tuple(analyse_day(demands, weekday, limit_kw) for weekday in WEEKDAYS)
    worst = max(days, key=lambda d: (d.peak_kw, -d.weekday))
    return ScheduleMetrics(
        monthly_kwh=model.month_kwh(year, month),
        weekly_energy_charge=weekly,
        monthly_bill=bill.total if bill else None,
        peak_kw=worst.peak_kw,
        peak_expected_kw=max(d.peak_expected_kw for d in days),
        peak_weekday=worst.weekday,
        minutes_over_limit=sum(d.minutes_over_limit for d in days),
        conflict_minutes=sum(c.window.minutes for d in days for c in d.conflicts),
        days=days,
    )
