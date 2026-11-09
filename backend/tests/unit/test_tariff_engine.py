"""Bill arithmetic, each expected value worked out by hand in the comments."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal as D

import pytest

from powershift.calculation.tariff_engine import compute_bill, slab_charge, step_prices
from powershift.domain.tariff import ChargeKind, DayType, SlabMode, TouPeriod
from powershift.domain.time_window import TimeWindow
from tests.factories import charge, flat_tariff, slab_tariff, tou_tariff


def test_flat_bill_with_all_charge_kinds() -> None:
    # energy   200 kWh x 5      = 1000.00
    # fixed                       =   50.00
    # per-kWh  200 x 0.25         =   50.00
    # subtotal                    = 1100.00
    # tax 5% of 1100              =   55.00
    # total                       = 1155.00
    tariff = flat_tariff(
        "5",
        (
            charge(ChargeKind.FIXED_MONTHLY, "50", "Meter rent"),
            charge(ChargeKind.PER_KWH, "0.25", "Fuel surcharge"),
            charge(ChargeKind.PERCENTAGE, "5", "Electricity duty"),
        ),
    )
    bill = compute_bill(tariff, D("200"), timed_charge=D("1000"))

    assert [(line.label, line.amount) for line in bill.lines] == [
        ("Energy charge", D("1000.00")),
        ("Meter rent", D("50.00")),
        ("Fuel surcharge", D("50.00")),
        ("Electricity duty", D("55.00")),
    ]
    assert bill.subtotal == D("1100.00")
    assert bill.total == D("1155.00")
    assert bill.effective_rate_per_kwh == D("5.775")


def test_several_percentages_apply_to_the_same_subtotal() -> None:
    # subtotal 100; 10% -> 10; 5% -> 5 (not 5% of 110)
    tariff = flat_tariff(
        "1", (charge(ChargeKind.PERCENTAGE, "10"), charge(ChargeKind.PERCENTAGE, "5"))
    )
    assert compute_bill(tariff, D("100"), D("100")).total == D("115.00")


def test_percentages_apply_to_the_printed_subtotal() -> None:
    # Energy 10.005 prints as 10.01. A 50% duty must be 50% of 10.01 = 5.005 -> 5.01,
    # not 50% of the unrounded 10.005 (= 5.0025 -> 5.00), or the bill can't be checked by hand.
    tariff = flat_tariff("1", (charge(ChargeKind.PERCENTAGE, "50"),))
    bill = compute_bill(tariff, D("10"), D("10.005"))
    assert [line.amount for line in bill.lines] == [D("10.01"), D("5.01")]
    assert bill.subtotal == D("10.01")
    assert bill.total == D("15.02")


def test_total_is_the_sum_of_the_rounded_lines() -> None:
    # 1/3 kWh-ish amounts: each line rounds separately; the total must add up exactly.
    tariff = flat_tariff("0.3333", (charge(ChargeKind.PERCENTAGE, "7.5"),))
    bill = compute_bill(tariff, D("10"), D("3.333"))
    assert bill.total == sum(line.amount for line in bill.lines)


@pytest.mark.parametrize(
    ("kwh", "telescopic", "whole_usage"),
    [
        ("80", "240", "240"),  # all in band 1: 80 x 3
        ("100", "300", "300"),  # exactly at the first limit
        ("150", "525", "675"),  # 100x3 + 50x4.5 = 525 | 150 x 4.5 = 675
        ("250", "1050", "1500"),  # 300 + 450 + 50x6 = 1050 | 250 x 6 = 1500
        ("0", "0", "0"),
    ],
)
def test_slab_charges(kwh: str, telescopic: str, whole_usage: str) -> None:
    slabs = slab_tariff().slabs
    assert slab_charge(slabs, SlabMode.TELESCOPIC, D(kwh))[0] == D(telescopic)
    assert slab_charge(slabs, SlabMode.WHOLE_USAGE, D(kwh))[0] == D(whole_usage)


def test_slab_breakdown_lists_each_band() -> None:
    _, uses = slab_charge(slab_tariff().slabs, SlabMode.TELESCOPIC, D("250"))
    assert [(u.from_kwh, u.kwh, u.rate_per_kwh) for u in uses] == [
        (D(0), D(100), D(3)),
        (D(100), D(100), D("4.5")),
        (D(200), D(50), D(6)),
    ]


def test_slab_bill_ignores_timed_charge_and_explains_bands() -> None:
    bill = compute_bill(slab_tariff(), D("150"), timed_charge=D("999"))
    assert bill.energy_charge == D("525.00")
    assert bill.lines[0].detail == "100 kWh @ 3 + 50 kWh @ 4.5"


def test_flat_step_prices() -> None:
    prices = step_prices(flat_tariff("6.5"), weekday=2)
    assert prices is not None
    assert set(prices) == {D("6.5")} and len(prices) == 96


def test_tou_step_prices_follow_periods() -> None:
    prices = step_prices(tou_tariff(), weekday=0)
    assert prices is not None
    assert prices[0] == D(3)  # 00:00
    assert prices[24] == D(5)  # 06:00
    assert prices[76] == D(8)  # 19:00
    assert prices[95] == D(3)  # 23:45


def test_tou_weekend_prices_differ_from_weekday() -> None:
    weekday = tuple(replace(p, day_type=DayType.WEEKDAY) for p in tou_tariff().tou_periods)
    weekend = (TouPeriod(TimeWindow(0, 1440), DayType.WEEKEND, D(4)),)
    tariff = tou_tariff(weekday + weekend)

    assert step_prices(tariff, 4)[76] == D(8)  # type: ignore[index]  # Friday 19:00
    assert step_prices(tariff, 5)[76] == D(4)  # type: ignore[index]  # Saturday 19:00


def test_slab_tariffs_have_no_time_prices() -> None:
    assert step_prices(slab_tariff(), 0) is None
