from __future__ import annotations

from fastapi import APIRouter

from powershift.api.deps import SessionDep
from powershift.schemas.household import HouseholdInput, HouseholdRead
from powershift.services.household_service import HouseholdService

router = APIRouter(prefix="/api/household", tags=["household"])


@router.get("", response_model=HouseholdRead | None)
def get_household(session: SessionDep) -> HouseholdRead | None:
    """Returns null until the household has been set up."""
    return HouseholdService(session).get()


@router.put("", response_model=HouseholdRead)
def save_household(session: SessionDep, data: HouseholdInput) -> HouseholdRead:
    return HouseholdService(session).save(data)
