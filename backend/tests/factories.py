"""Reusable test data. Values are realistic but are test fixtures, not product data."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from typing import Any

from powershift.domain.appliance import (
    ApplianceCategory,
    ApplianceMode,
    ApplianceSpec,
    FlexibleSchedule,
    Priority,
)
from powershift.domain.tariff import (
    Charge,
    ChargeKind,
    DayType,
    Slab,
    SlabMode,
    TariffSpec,
    TariffType,
    TouPeriod,
)
from powershift.domain.time_window import TimeWindow

ALL_WEEK = (0, 1, 2, 3, 4, 5, 6)


def fixed_spec(**changes: Any) -> ApplianceSpec:
    spec = ApplianceSpec(
        name="Refrigerator",
        category=ApplianceCategory.KITCHEN,
        rated_power_w=150,
        quantity=1,
        duty_cycle=0.4,
        mode=ApplianceMode.FIXED,
        priority=Priority.HIGH,
        allow_simultaneous=True,
        operating_days=ALL_WEEK,
        fixed_blocks=(TimeWindow(0, 1440),),
        flexible=None,
    )
    return replace(spec, **changes)


def flexible_schedule(**changes: Any) -> FlexibleSchedule:
    schedule = FlexibleSchedule(
        run_duration_minutes=90,
        allowed_window=TimeWindow(480, 1320),  # 08:00-22:00
        current_start_minute=1140,  # 19:00
        preferred_window=None,
        must_be_contiguous=True,
    )
    return replace(schedule, **changes)


def flexible_spec(**changes: Any) -> ApplianceSpec:
    spec = fixed_spec(
        name="Washing machine",
        category=ApplianceCategory.LAUNDRY,
        rated_power_w=2000,
        duty_cycle=0.5,
        mode=ApplianceMode.FLEXIBLE,
        priority=Priority.MEDIUM,
        allow_simultaneous=False,
        operating_days=(0, 3, 5),
        fixed_blocks=(),
        flexible=flexible_schedule(),
    )
    return replace(spec, **changes)


def fixed_payload(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "Refrigerator",
        "category": "kitchen",
        "rated_power_w": 150,
        "quantity": 1,
        "duty_cycle": 0.4,
        "mode": "fixed",
        "priority": "high",
        "allow_simultaneous": True,
        "operating_days": [0, 1, 2, 3, 4, 5, 6],
        "fixed_blocks": [{"start_minute": 0, "end_minute": 1440}],
        "flexible": None,
    }
    payload.update(changes)
    return payload


def flexible_payload(**changes: Any) -> dict[str, Any]:
    payload = fixed_payload(
        name="Washing machine",
        category="laundry",
        rated_power_w=2000,
        duty_cycle=0.5,
        mode="flexible",
        priority="medium",
        allow_simultaneous=False,
        operating_days=[0, 3, 5],
        fixed_blocks=[],
        flexible={
            "run_duration_minutes": 90,
            "earliest_start_minute": 480,
            "latest_end_minute": 1320,
            "current_start_minute": 1140,
            "preferred_start_minute": None,
            "preferred_end_minute": None,
            "must_be_contiguous": True,
        },
    )
    payload.update(changes)
    return payload


HOUSEHOLD_PAYLOAD: dict[str, Any] = {
    "name": "Test home",
    "occupants": 4,
    "location_label": "Chennai",
    "max_load_kw": 5,
    "currency_code": "INR",
    "time_format": "24h",
}


# --- Tariffs ------------------------------------------------------------------------
# Rates below are invented round numbers for arithmetic tests, not real utility rates.


def flat_tariff(rate: str = "5", charges: tuple[Charge, ...] = ()) -> TariffSpec:
    return TariffSpec(
        name="Flat test tariff",
        tariff_type=TariffType.FLAT,
        effective_date=date(2026, 1, 1),
        flat_rate_per_kwh=D(rate),
        tou_periods=(),
        slabs=(),
        slab_mode=SlabMode.TELESCOPIC,
        charges=charges,
    )


def tou_periods_all_days() -> tuple[TouPeriod, ...]:
    """00-06 @3, 06-18 @5, 18-22 @8 (peak), 22-24 @3."""
    return (
        TouPeriod(TimeWindow(0, 360), DayType.ALL, D("3")),
        TouPeriod(TimeWindow(360, 1080), DayType.ALL, D("5")),
        TouPeriod(TimeWindow(1080, 1320), DayType.ALL, D("8")),
        TouPeriod(TimeWindow(1320, 1440), DayType.ALL, D("3")),
    )


def tou_tariff(periods: tuple[TouPeriod, ...] | None = None) -> TariffSpec:
    return replace(
        flat_tariff(),
        name="TOU test tariff",
        tariff_type=TariffType.TOU,
        flat_rate_per_kwh=None,
        tou_periods=periods if periods is not None else tou_periods_all_days(),
    )


def slab_tariff(mode: SlabMode = SlabMode.TELESCOPIC) -> TariffSpec:
    """0-100 kWh @3, 100-200 @4.5, above 200 @6."""
    return replace(
        flat_tariff(),
        name="Slab test tariff",
        tariff_type=TariffType.SLAB,
        flat_rate_per_kwh=None,
        slabs=(Slab(D("100"), D("3")), Slab(D("200"), D("4.5")), Slab(None, D("6"))),
        slab_mode=mode,
    )


def charge(kind: ChargeKind, amount: str, label: str = "Charge") -> Charge:
    return Charge(kind, label, D(amount))
