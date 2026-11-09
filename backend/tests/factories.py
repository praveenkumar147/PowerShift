"""Reusable test data. Values are realistic but are test fixtures, not product data."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from powershift.domain.appliance import (
    ApplianceCategory,
    ApplianceMode,
    ApplianceSpec,
    FlexibleSchedule,
    Priority,
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
