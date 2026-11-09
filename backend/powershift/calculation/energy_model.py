"""Household energy and cost over days, months and date ranges.

Key idea: every Monday in the model is the same typical Monday. So we compute
each appliance's energy (and time-priced cost) once per weekday, and any period
is just "how many Mondays, Tuesdays, ... does it contain" x those values.

Cost rules:
- Flat and time-of-use tariffs: costs are exact per step, so any period and any
  single appliance can be priced directly.
- Slab tariffs: the price depends on the MONTHLY total of the whole household.
  An appliance's or a single day's share is priced at that month's average
  energy rate (energy charge / kWh). This is stated in the report notes.
- Period and appliance figures are ENERGY CHARGES only. Fixed monthly charges
  and taxes appear in the monthly bill.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from powershift.calculation.load_profile import STEP_HOURS, WEEKDAYS, ApplianceLoad
from powershift.calculation.tariff_engine import (
    Bill,
    compute_bill,
    kwh_by_price,
    priced_energy_charge,
    step_prices,
    to_decimal_kwh,
)
from powershift.domain.appliance import ApplianceCategory, ApplianceMode
from powershift.domain.tariff import TariffSpec, TariffType

STEPS_PER_HOUR = 4
HOURS_PER_DAY = 24
MAX_RANGE_DAYS = 366


def weekday_counts(start: date, end: date) -> list[int]:
    """How many of each weekday (Mon..Sun) fall in [start, end], inclusive."""
    days = (end - start).days + 1
    counts = [days // 7] * 7
    for offset in range(days % 7):
        counts[(start.weekday() + offset) % 7] += 1
    return counts


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def months_in(start: date, end: date) -> list[tuple[int, int]]:
    months: list[tuple[int, int]] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


@dataclass(frozen=True, slots=True)
class ApplianceTotal:
    load: ApplianceLoad
    kwh: float
    energy_charge: Decimal | None


@dataclass(frozen=True, slots=True)
class DayTotal:
    day: date
    kwh: float
    energy_charge: Decimal | None


@dataclass(frozen=True, slots=True)
class PeriodReport:
    start: date
    end: date
    total_kwh: float
    energy_charge: Decimal | None
    daily: tuple[DayTotal, ...]
    appliances: tuple[ApplianceTotal, ...]
    """Sorted by kWh, highest first."""

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass(frozen=True, slots=True)
class HourTotal:
    hour: int
    kwh: float
    fixed_kwh: float
    flexible_kwh: float
    price_per_kwh: Decimal | None
    """Average price in this hour; None for slab tariffs or when it varies by day."""


@dataclass(frozen=True, slots=True)
class MonthTotal:
    month: int
    days: int
    kwh: float
    bill_total: Decimal | None


class EnergyModel:
    def __init__(self, loads: Sequence[ApplianceLoad], tariff: TariffSpec | None) -> None:
        self.loads = list(loads)
        self.tariff = tariff
        self._prices = [step_prices(tariff, w) for w in WEEKDAYS] if tariff else [None] * 7
        # Per appliance, per weekday: energy, and its time-priced charge (flat/TOU only).
        self._kwh = {load.appliance_id: [load.day_kwh(w) for w in WEEKDAYS] for load in self.loads}
        self._timed = {
            load.appliance_id: [self._timed_charge(load, w) for w in WEEKDAYS]
            for load in self.loads
        }
        self._slab_rate_cache: dict[tuple[int, int], Decimal] = {}

    @property
    def is_slab(self) -> bool:
        return self.tariff is not None and self.tariff.tariff_type is TariffType.SLAB

    def _timed_charge(self, load: ApplianceLoad, weekday: int) -> Decimal | None:
        prices = self._prices[weekday]
        if prices is None:
            return None
        return priced_energy_charge(kwh_by_price(load.profiles[weekday], prices, STEP_HOURS))

    def _select(self, category: ApplianceCategory | None) -> list[ApplianceLoad]:
        return [load for load in self.loads if category is None or load.category is category]

    # --- Whole-household monthly bill ---------------------------------------------

    def month_kwh(self, year: int, month: int) -> float:
        counts = weekday_counts(*month_bounds(year, month))
        return sum(counts[w] * kwh[w] for kwh in self._kwh.values() for w in WEEKDAYS)

    def month_bill(self, year: int, month: int) -> Bill | None:
        if self.tariff is None:
            return None
        counts = weekday_counts(*month_bounds(year, month))
        timed = Decimal(0)
        if not self.is_slab:
            timed = sum(
                (
                    counts[w] * (charges[w] or Decimal(0))
                    for charges in self._timed.values()
                    for w in WEEKDAYS
                ),
                Decimal(0),
            )
        return compute_bill(self.tariff, to_decimal_kwh(self.month_kwh(year, month)), timed)

    def _slab_average_rate(self, year: int, month: int) -> Decimal:
        key = (year, month)
        if key not in self._slab_rate_cache:
            bill = self.month_bill(year, month)
            assert bill is not None
            self._slab_rate_cache[key] = (
                bill.energy_charge / bill.total_kwh if bill.total_kwh else Decimal(0)
            )
        return self._slab_rate_cache[key]

    # --- Period report ----------------------------------------------------------------

    def _charge(
        self, appliance_id: int, weekday: int, count: int, year: int, month: int
    ) -> Decimal | None:
        if self.tariff is None or count == 0:
            return None if self.tariff is None else Decimal(0)
        if self.is_slab:
            return to_decimal_kwh(
                self._kwh[appliance_id][weekday] * count
            ) * self._slab_average_rate(year, month)
        timed = self._timed[appliance_id][weekday]
        assert timed is not None
        return timed * count

    def period_report(
        self, start: date, end: date, category: ApplianceCategory | None = None
    ) -> PeriodReport:
        if end < start:
            raise ValueError("The end date is before the start date.")
        if (end - start).days + 1 > MAX_RANGE_DAYS:
            raise ValueError(f"Choose a range of at most {MAX_RANGE_DAYS} days.")
        selected = self._select(category)
        priced = self.tariff is not None

        appliance_kwh: dict[int, float] = defaultdict(float)
        appliance_charge: dict[int, Decimal] = defaultdict(Decimal)
        for year, month in months_in(start, end):
            first, last = month_bounds(year, month)
            counts = weekday_counts(max(first, start), min(last, end))
            for load in selected:
                for w in WEEKDAYS:
                    appliance_kwh[load.appliance_id] += counts[w] * self._kwh[load.appliance_id][w]
                    charge = self._charge(load.appliance_id, w, counts[w], year, month)
                    if charge is not None:
                        appliance_charge[load.appliance_id] += charge

        daily = []
        current = start
        while current <= end:
            w = current.weekday()
            day_charge = (
                sum(
                    (
                        self._charge(load.appliance_id, w, 1, current.year, current.month)
                        or Decimal(0)
                        for load in selected
                    ),
                    Decimal(0),
                )
                if priced
                else None
            )
            daily.append(
                DayTotal(
                    current, sum(self._kwh[load.appliance_id][w] for load in selected), day_charge
                )
            )
            current += timedelta(days=1)

        appliances = sorted(
            (
                ApplianceTotal(
                    load,
                    appliance_kwh[load.appliance_id],
                    appliance_charge[load.appliance_id] if priced else None,
                )
                for load in selected
            ),
            key=lambda a: (-a.kwh, a.load.name.lower()),
        )
        return PeriodReport(
            start=start,
            end=end,
            total_kwh=sum(a.kwh for a in appliances),
            energy_charge=sum((a.energy_charge or Decimal(0) for a in appliances), Decimal(0))
            if priced
            else None,
            daily=tuple(daily),
            appliances=tuple(appliances),
        )

    # --- Hourly profile ----------------------------------------------------------------

    def hourly_profile(
        self, weekday: int | None, category: ApplianceCategory | None = None
    ) -> list[HourTotal]:
        """Energy per hour on a given weekday, or averaged over the week when weekday is None."""
        weekdays = [weekday] if weekday is not None else list(WEEKDAYS)
        selected = self._select(category)
        rows = []
        for hour in range(HOURS_PER_DAY):
            steps = range(hour * STEPS_PER_HOUR, (hour + 1) * STEPS_PER_HOUR)
            fixed = flexible = 0.0
            for load in selected:
                kwh = (
                    sum(load.profiles[w][s] for w in weekdays for s in steps)
                    * STEP_HOURS
                    / len(weekdays)
                )
                if load.mode is ApplianceMode.FIXED:
                    fixed += kwh
                else:
                    flexible += kwh
            rows.append(
                HourTotal(
                    hour, fixed + flexible, fixed, flexible, self._hour_price(weekdays, steps)
                )
            )
        return rows

    def _hour_price(self, weekdays: list[int], steps: range) -> Decimal | None:
        averages = set()
        for w in weekdays:
            prices = self._prices[w]
            if prices is None:
                return None
            averages.add(sum((prices[s] for s in steps), Decimal(0)) / len(steps))
        return averages.pop() if len(averages) == 1 else None

    # --- Monthly projection ----------------------------------------------------------

    def monthly_projection(
        self, year: int, category: ApplianceCategory | None = None
    ) -> list[MonthTotal]:
        selected_ids = {load.appliance_id for load in self._select(category)}
        rows = []
        for month in range(1, 13):
            first, last = month_bounds(year, month)
            counts = weekday_counts(first, last)
            kwh = sum(counts[w] * self._kwh[i][w] for i in selected_ids for w in WEEKDAYS)
            bill = self.month_bill(year, month)
            rows.append(MonthTotal(month, last.day, kwh, bill.total if bill else None))
        return rows
