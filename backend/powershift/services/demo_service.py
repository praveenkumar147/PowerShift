"""Sample data so a new user can explore the app before entering their own.

Everything created here is labelled as sample data, and the tariff rates are
invented round numbers, NOT a real utility's prices. Loading is only allowed
into an empty database so it can never mix with or overwrite real data.
The data goes through the normal services, so it obeys every validation rule.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from powershift.core.errors import ConflictError
from powershift.db.models import Appliance, Household, Tariff
from powershift.schemas.appliance import ApplianceInput
from powershift.schemas.household import HouseholdInput
from powershift.schemas.tariff import TariffInput
from powershift.services.appliance_service import ApplianceService
from powershift.services.household_service import HouseholdService
from powershift.services.tariff_service import TariffService

SAMPLE_HOUSEHOLD = "Sample household (demo data)"
SAMPLE_TARIFF = "Sample time-of-use tariff (invented rates, not a real utility tariff)"
EVERY_DAY = [0, 1, 2, 3, 4, 5, 6]
ALL_DAY = [{"start_minute": 0, "end_minute": 1440}]


def _hhmm(text: str) -> int:
    hours, minutes = text.split(":")
    return int(hours) * 60 + int(minutes)


def _fixed(
    name: str,
    category: str,
    watts: float,
    blocks: list[tuple[str, str]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "name": name,
        "category": category,
        "rated_power_w": watts,
        "quantity": extra.pop("quantity", 1),
        "duty_cycle": extra.pop("duty_cycle", 1.0),
        "mode": "fixed",
        "priority": extra.pop("priority", "medium"),
        "operating_days": extra.pop("operating_days", EVERY_DAY),
        "fixed_blocks": ALL_DAY
        if blocks is None
        else [{"start_minute": _hhmm(s), "end_minute": _hhmm(e) or 1440} for s, e in blocks],
    }


def _flexible(
    name: str,
    category: str,
    watts: float,
    duration: int,
    window: tuple[str, str],
    usual: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "name": name,
        "category": category,
        "rated_power_w": watts,
        "quantity": 1,
        "duty_cycle": extra.pop("duty_cycle", 1.0),
        "mode": "flexible",
        "priority": "medium",
        "allow_simultaneous": extra.pop("allow_simultaneous", False),
        "operating_days": extra.pop("operating_days", EVERY_DAY),
        "flexible": {
            "run_duration_minutes": duration,
            "earliest_start_minute": _hhmm(window[0]),
            "latest_end_minute": _hhmm(window[1]) or 1440,
            "current_start_minute": _hhmm(usual),
            "must_be_contiguous": True,
        },
    }


SAMPLE_APPLIANCES = [
    _fixed("Refrigerator", "kitchen", 150, duty_cycle=0.4, priority="high"),
    _fixed("Wi-Fi router", "electronics", 12, priority="high"),
    _fixed("LED lights", "lighting", 9, [("06:00", "07:00"), ("18:00", "23:00")], quantity=8),
    _fixed("Ceiling fans", "cooling", 75, [("13:00", "16:00"), ("22:00", "06:00")], quantity=3),
    _fixed("Television", "entertainment", 100, [("19:00", "22:00")]),
    _fixed("Air conditioner", "cooling", 1500, [("22:00", "05:00")], duty_cycle=0.6),
    _flexible(
        "Washing machine",
        "laundry",
        2000,
        90,
        ("06:00", "23:00"),
        "19:00",
        duty_cycle=0.5,
        operating_days=[0, 3, 5],
    ),
    _flexible("Dishwasher", "kitchen", 1800, 120, ("20:00", "07:00"), "20:30", duty_cycle=0.6),
    _flexible("Water heater", "water_heating", 3000, 60, ("04:00", "09:00"), "07:00"),
]

SAMPLE_TARIFF_BODY = {
    "name": SAMPLE_TARIFF,
    "tariff_type": "tou",
    "effective_date": date(2026, 1, 1),
    "tou_periods": [
        {"day_type": "all", "start_minute": 0, "end_minute": 360, "rate_per_kwh": "4.50"},
        {"day_type": "all", "start_minute": 360, "end_minute": 1080, "rate_per_kwh": "6.00"},
        {"day_type": "all", "start_minute": 1080, "end_minute": 1320, "rate_per_kwh": "8.50"},
        {"day_type": "all", "start_minute": 1320, "end_minute": 1440, "rate_per_kwh": "4.50"},
    ],
    "charges": [
        {"kind": "fixed_monthly", "label": "Fixed charge (sample)", "amount": "120"},
        {"kind": "per_kwh", "label": "Fuel adjustment (sample)", "amount": "0.30"},
        {"kind": "percentage", "label": "Electricity duty (sample)", "amount": "5"},
    ],
}

SAMPLE_HOUSEHOLD_BODY = {
    "name": SAMPLE_HOUSEHOLD,
    "occupants": 4,
    "location_label": None,
    "max_load_kw": 5,
    "currency_code": "INR",
    "time_format": "24h",
}


class DemoService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def load(self) -> dict[str, int]:
        if self._has_data():
            raise ConflictError(
                "Sample data can only be loaded into an empty database, "
                "so it never mixes with your own data."
            )
        HouseholdService(self._session).save(HouseholdInput.model_validate(SAMPLE_HOUSEHOLD_BODY))
        TariffService(self._session).create(TariffInput.model_validate(SAMPLE_TARIFF_BODY))
        appliances = ApplianceService(self._session)
        for body in SAMPLE_APPLIANCES:
            appliances.create(ApplianceInput.model_validate(body))
        return {"appliances": len(SAMPLE_APPLIANCES), "tariffs": 1}

    def _has_data(self) -> bool:
        return any(
            self._session.scalar(select(func.count()).select_from(model))
            for model in (Household, Appliance, Tariff)
        )
