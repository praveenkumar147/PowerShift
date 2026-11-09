"""Appliance endpoints. Routes only translate HTTP <-> service calls."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from powershift.api.deps import SessionDep
from powershift.domain.appliance import ApplianceCategory, ApplianceMode
from powershift.schemas.appliance import ApplianceInput, ApplianceRead
from powershift.services.appliance_service import ApplianceService

router = APIRouter(prefix="/api/appliances", tags=["appliances"])


@router.get("", response_model=list[ApplianceRead])
def list_appliances(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=100, description="Search in names")] = None,
    category: ApplianceCategory | None = None,
    mode: ApplianceMode | None = None,
) -> list[ApplianceRead]:
    return ApplianceService(session).list(q.strip() if q else None, category, mode)


@router.post("", response_model=ApplianceRead, status_code=status.HTTP_201_CREATED)
def create_appliance(session: SessionDep, data: ApplianceInput) -> ApplianceRead:
    return ApplianceService(session).create(data)


@router.get("/{appliance_id}", response_model=ApplianceRead)
def get_appliance(session: SessionDep, appliance_id: int) -> ApplianceRead:
    return ApplianceService(session).get(appliance_id)


@router.put("/{appliance_id}", response_model=ApplianceRead)
def update_appliance(session: SessionDep, appliance_id: int, data: ApplianceInput) -> ApplianceRead:
    return ApplianceService(session).update(appliance_id, data)


@router.delete("/{appliance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appliance(session: SessionDep, appliance_id: int) -> Response:
    ApplianceService(session).delete(appliance_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
