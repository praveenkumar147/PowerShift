"""Household profile domain model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TimeFormat(StrEnum):
    H12 = "12h"
    H24 = "24h"


@dataclass(frozen=True, slots=True)
class HouseholdProfile:
    name: str
    occupants: int
    location_label: str | None
    """Free text for the user's reference. Never used to guess a tariff."""
    max_load_kw: float
    """Connection limit: total power the house may draw at one instant (kW, not kWh)."""
    currency_code: str
    time_format: TimeFormat
