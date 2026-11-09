"""Tariff endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from powershift.api.deps import SessionDep
from powershift.schemas.tariff import TariffInput, TariffRead
from powershift.services.tariff_service import TariffService

router = APIRouter(prefix="/api/tariffs", tags=["tariffs"])


@router.get("", response_model=list[TariffRead])
def list_tariffs(session: SessionDep) -> list[TariffRead]:
    """Active tariff first, then by name."""
    return TariffService(session).list()


@router.post("", response_model=TariffRead, status_code=status.HTTP_201_CREATED)
def create_tariff(session: SessionDep, data: TariffInput) -> TariffRead:
    """The first tariff created becomes the active one."""
    return TariffService(session).create(data)


@router.get("/{tariff_id}", response_model=TariffRead)
def get_tariff(session: SessionDep, tariff_id: int) -> TariffRead:
    return TariffService(session).get(tariff_id)


@router.put("/{tariff_id}", response_model=TariffRead)
def update_tariff(session: SessionDep, tariff_id: int, data: TariffInput) -> TariffRead:
    return TariffService(session).update(tariff_id, data)


@router.delete("/{tariff_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tariff(session: SessionDep, tariff_id: int) -> Response:
    TariffService(session).delete(tariff_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{tariff_id}/activate", response_model=TariffRead)
def activate_tariff(session: SessionDep, tariff_id: int) -> TariffRead:
    return TariffService(session).activate(tariff_id)
