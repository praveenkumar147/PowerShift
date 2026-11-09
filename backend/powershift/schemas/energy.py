"""Response models for energy analysis and bill estimates.

kWh values are rounded to 3 decimals (1 Wh) and money to 2 decimals for display;
calculations use full precision.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from powershift.calculation.tariff_engine import money
from powershift.domain.appliance import ApplianceCategory, ApplianceMode
from powershift.domain.tariff import TariffType

KWH_DECIMALS = 3


def kwh_out(value: float) -> float:
    return round(value, KWH_DECIMALS)


def money_out(value: Decimal | None) -> float | None:
    return None if value is None else float(money(value))


class TariffSummary(BaseModel):
    id: int
    name: str
    tariff_type: TariffType


class DayRow(BaseModel):
    date: date
    kwh: float
    energy_charge: float | None


class ApplianceRow(BaseModel):
    appliance_id: int
    name: str
    category: ApplianceCategory
    mode: ApplianceMode
    kwh: float
    share: float
    """Fraction (0-1) of the reported total."""
    energy_charge: float | None


class CategoryRow(BaseModel):
    category: ApplianceCategory
    kwh: float
    share: float
    energy_charge: float | None


class EnergyReport(BaseModel):
    start: date
    end: date
    days: int
    total_kwh: float
    average_daily_kwh: float
    energy_charge: float | None
    tariff: TariffSummary | None
    daily: list[DayRow]
    appliances: list[ApplianceRow]
    categories: list[CategoryRow]
    notes: list[str]


class HourRow(BaseModel):
    hour: int
    kwh: float
    fixed_kwh: float
    flexible_kwh: float
    price_per_kwh: float | None


class HourlyProfile(BaseModel):
    weekday: int | None
    hours: list[HourRow]
    tariff: TariffSummary | None
    notes: list[str]


class MonthRow(BaseModel):
    month: int
    days: int
    kwh: float
    bill_total: float | None


class MonthlyProjection(BaseModel):
    year: int
    months: list[MonthRow]
    tariff: TariffSummary | None
    notes: list[str]


class BillLineRead(BaseModel):
    label: str
    kind: str
    amount: float
    detail: str


class BillEstimate(BaseModel):
    year: int
    month: int
    days: int
    total_kwh: float
    tariff: TariffSummary | None
    lines: list[BillLineRead]
    subtotal: float | None
    total: float | None
    effective_rate_per_kwh: float | None
    notes: list[str]
