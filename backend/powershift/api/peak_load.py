"""Peak load endpoint. All values are kW (power), not kWh (energy)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from powershift.api.deps import SessionDep
from powershift.schemas.peak_load import PeakLoadAnalysis
from powershift.services.peak_load_service import PeakLoadService

router = APIRouter(prefix="/api/peak-load", tags=["peak load"])


@router.get("/analysis", response_model=PeakLoadAnalysis)
def peak_load_analysis(
    session: SessionDep,
    weekday: Annotated[
        int | None,
        Query(ge=0, le=6, description="0 = Monday; omit to analyse the day with the highest peak"),
    ] = None,
) -> PeakLoadAnalysis:
    return PeakLoadService(session).analysis(weekday)
