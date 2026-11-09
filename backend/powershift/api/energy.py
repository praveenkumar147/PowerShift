"""Energy analysis endpoints. All figures are estimates from user-entered settings."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from powershift.api.deps import SessionDep
from powershift.domain.appliance import ApplianceCategory
from powershift.schemas.energy import BillEstimate, EnergyReport, HourlyProfile, MonthlyProjection
from powershift.services.energy_service import EnergyService

router = APIRouter(prefix="/api/energy", tags=["energy"])

Year = Annotated[int, Query(ge=2000, le=2100)]


@router.get("/report", response_model=EnergyReport)
def energy_report(
    session: SessionDep,
    start: date,
    end: date,
    category: ApplianceCategory | None = None,
) -> EnergyReport:
    """Energy and energy charges for a date range: totals, daily series and breakdowns."""
    return EnergyService(session).report(start, end, category)


@router.get("/hourly-profile", response_model=HourlyProfile)
def hourly_profile(
    session: SessionDep,
    weekday: Annotated[
        int | None, Query(ge=0, le=6, description="0 = Monday; omit for the weekly average")
    ] = None,
    category: ApplianceCategory | None = None,
) -> HourlyProfile:
    return EnergyService(session).hourly_profile(weekday, category)


@router.get("/monthly", response_model=MonthlyProjection)
def monthly_projection(
    session: SessionDep, year: Year, category: ApplianceCategory | None = None
) -> MonthlyProjection:
    return EnergyService(session).monthly(year, category)


@router.get("/bill", response_model=BillEstimate)
def bill_estimate(
    session: SessionDep, year: Year, month: Annotated[int, Query(ge=1, le=12)]
) -> BillEstimate:
    """Itemised bill estimate for one calendar month, for the whole household."""
    return EnergyService(session).bill(year, month)
