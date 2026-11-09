"""Energy model: profiles, periods, months and hours, checked against hand calculations.

Household used throughout:
- Fridge: 150 W x 0.4 duty = 0.06 kW average, all day, every day -> 1.44 kWh/day.
- Washer: 2000 W x 0.5 duty = 1 kW average, 90 min from 19:00, on Mon, Thu, Sat
  -> 1.5 kWh per operating day.
TOU tariff: 00-06 @3, 06-18 @5, 18-22 @8, 22-24 @3.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from powershift.calculation.energy_model import EnergyModel, weekday_counts
from powershift.calculation.load_profile import build_loads
from powershift.domain.appliance import ApplianceCategory
from powershift.domain.time_window import TimeWindow
from tests.factories import (
    fixed_spec,
    flat_tariff,
    flexible_schedule,
    flexible_spec,
    slab_tariff,
    tou_tariff,
)

FRIDGE_ID, WASHER_ID = 1, 2
WASHER_DAYS = (0, 3, 5)


def household(tariff=None) -> EnergyModel:  # type: ignore[no-untyped-def]
    loads = build_loads(
        [
            (FRIDGE_ID, fixed_spec()),
            (WASHER_ID, flexible_spec(flexible=flexible_schedule(current_start_minute=1140))),
        ]
    )
    return EnergyModel(loads, tariff)


def naive_counts(start: date, end: date) -> list[int]:
    counts = [0] * 7
    day = start
    while day <= end:
        counts[day.weekday()] += 1
        day += timedelta(days=1)
    return counts


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 11, 1), date(2026, 11, 30)),
        (date(2026, 2, 1), date(2026, 2, 28)),
        (date(2024, 2, 1), date(2024, 2, 29)),  # leap year
        (date(2026, 11, 9), date(2026, 11, 9)),
        (date(2025, 12, 20), date(2026, 1, 13)),
    ],
)
def test_weekday_counts_match_a_day_by_day_count(start: date, end: date) -> None:
    assert weekday_counts(start, end) == naive_counts(start, end)


def test_month_energy() -> None:
    # November 2026 starts on a Sunday: 30 days; Mon x5, Thu x4, Sat x4 = 13 washer days.
    # 30 x 1.44 + 13 x 1.5 = 43.2 + 19.5 = 62.7 kWh
    assert household().month_kwh(2026, 11) == pytest.approx(62.7)


def test_daily_tou_charge() -> None:
    # Fridge per day: 0.06 kW x (6h@3 + 12h@5 + 4h@8 + 2h@3) = 0.06 x 116 = 6.96
    # Washer 19:00-20:30 entirely in the 8.00 peak: 1.5 kWh x 8 = 12.00
    report = household(tou_tariff()).period_report(date(2026, 11, 9), date(2026, 11, 10))
    monday, tuesday = report.daily

    assert monday.kwh == pytest.approx(2.94)
    assert monday.energy_charge == D("18.96")
    assert tuesday.kwh == pytest.approx(1.44)
    assert tuesday.energy_charge == D("6.96")


def test_moving_the_washer_off_peak_lowers_tou_cost() -> None:
    off_peak = build_loads(
        [
            (
                WASHER_ID,
                flexible_spec(
                    flexible=flexible_schedule(
                        allowed_window=TimeWindow(0, 1440), current_start_minute=60
                    )
                ),
            )
        ]
    )
    report = EnergyModel(off_peak, tou_tariff()).period_report(date(2026, 11, 9), date(2026, 11, 9))
    assert report.energy_charge == D("4.50")  # 1.5 kWh x 3


def test_period_report_appliance_breakdown_sorted_by_energy() -> None:
    # November 2026 with TOU: fridge 30 x 1.44 = 43.2 kWh, 30 x 6.96 = 208.80
    #                         washer 13 x 1.5 = 19.5 kWh, 13 x 12   = 156.00
    report = household(tou_tariff()).period_report(date(2026, 11, 1), date(2026, 11, 30))

    fridge, washer = report.appliances
    assert fridge.load.appliance_id == FRIDGE_ID
    assert fridge.kwh == pytest.approx(43.2) and fridge.energy_charge == D("208.80")
    assert washer.kwh == pytest.approx(19.5) and washer.energy_charge == D("156.00")
    assert report.total_kwh == pytest.approx(62.7)
    assert report.energy_charge == D("364.80")
    assert report.days == 30 and len(report.daily) == 30


def test_category_filter() -> None:
    report = household(flat_tariff()).period_report(
        date(2026, 11, 1), date(2026, 11, 30), ApplianceCategory.LAUNDRY
    )
    assert [a.load.appliance_id for a in report.appliances] == [WASHER_ID]
    assert report.energy_charge == D("97.5")  # 19.5 kWh x 5


def test_without_tariff_costs_are_none_but_energy_is_known() -> None:
    report = household(None).period_report(date(2026, 11, 1), date(2026, 11, 7))
    assert report.energy_charge is None
    assert all(day.energy_charge is None for day in report.daily)
    assert report.total_kwh > 0
    assert household(None).month_bill(2026, 11) is None


def test_slab_month_bill_and_average_rate_allocation() -> None:
    # 62.7 kWh, all inside the first 100 kWh band @3 -> 188.10
    model = household(slab_tariff())
    bill = model.month_bill(2026, 11)
    assert bill is not None and bill.total == D("188.10")

    report = model.period_report(date(2026, 11, 1), date(2026, 11, 30))
    # Appliance shares are priced at the month's average rate (3.00 here).
    assert report.appliances[0].energy_charge == pytest.approx(D("129.6"), abs=D("0.001"))
    assert report.energy_charge == pytest.approx(bill.energy_charge, abs=D("0.001"))


def test_range_spanning_two_months() -> None:
    report = household(flat_tariff()).period_report(date(2026, 11, 30), date(2026, 12, 1))
    assert [d.day for d in report.daily] == [date(2026, 11, 30), date(2026, 12, 1)]
    assert report.total_kwh == pytest.approx(1.44 * 2 + 1.5)  # 30 Nov is a Monday


def test_invalid_ranges_are_rejected() -> None:
    with pytest.raises(ValueError, match="before"):
        household().period_report(date(2026, 11, 2), date(2026, 11, 1))
    with pytest.raises(ValueError, match="366"):
        household().period_report(date(2026, 1, 1), date(2027, 1, 2))


def test_hourly_profile_for_a_washer_day() -> None:
    hours = household(tou_tariff()).hourly_profile(weekday=0)

    assert len(hours) == 24
    assert hours[3].kwh == pytest.approx(0.06) and hours[3].flexible_kwh == 0
    assert hours[19].flexible_kwh == pytest.approx(1.0)  # 19:00-20:00 full hour at 1 kW
    assert hours[20].flexible_kwh == pytest.approx(0.5)  # 20:00-20:30
    assert hours[19].fixed_kwh == pytest.approx(0.06)
    assert hours[19].price_per_kwh == D(8)
    assert sum(h.kwh for h in hours) == pytest.approx(2.94)


def test_hourly_profile_averaged_over_the_week() -> None:
    hours = household(tou_tariff()).hourly_profile(weekday=None)
    # Washer runs 3 of 7 days: average 3/7 kWh in hour 19.
    assert hours[19].flexible_kwh == pytest.approx(3 / 7)
    assert hours[19].price_per_kwh == D(8)  # same price every day


def test_monthly_projection_has_twelve_months_with_bills() -> None:
    months = household(flat_tariff()).monthly_projection(2026)
    assert [m.month for m in months] == list(range(1, 13))
    november = months[10]
    assert november.days == 30
    assert november.kwh == pytest.approx(62.7)
    assert november.bill_total == D("313.50")  # 62.7 x 5
