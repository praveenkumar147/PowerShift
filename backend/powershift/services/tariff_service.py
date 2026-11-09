"""Tariff use cases."""

from __future__ import annotations

from sqlalchemy.orm import Session

from powershift.core.errors import NotFoundError, ValidationFailedError
from powershift.db.models import Tariff
from powershift.db.repositories.tariffs import TariffRepository, apply_spec, to_spec
from powershift.domain.tariff import TariffSpec, validate_tariff
from powershift.schemas.tariff import TariffInput, TariffRead


class TariffService:
    def __init__(self, session: Session) -> None:
        self._tariffs = TariffRepository(session)

    def list(self) -> list[TariffRead]:
        return [_to_read(row) for row in self._tariffs.list()]

    def get(self, tariff_id: int) -> TariffRead:
        return _to_read(self._require(tariff_id))

    def create(self, data: TariffInput) -> TariffRead:
        spec = _validated(data)
        is_first = self._tariffs.count() == 0
        row = self._tariffs.add(spec)
        if is_first:
            # The first tariff becomes active so calculations work immediately.
            self._tariffs.make_active(row)
        return _to_read(row)

    def update(self, tariff_id: int, data: TariffInput) -> TariffRead:
        row = self._require(tariff_id)
        apply_spec(row, _validated(data))
        return _to_read(row)

    def delete(self, tariff_id: int) -> None:
        # Deleting the active tariff is allowed; costs then show as unavailable
        # until another tariff is activated.
        self._tariffs.delete(self._require(tariff_id))

    def activate(self, tariff_id: int) -> TariffRead:
        row = self._require(tariff_id)
        self._tariffs.make_active(row)
        return _to_read(row)

    def active_spec(self) -> tuple[int, TariffSpec] | None:
        row = self._tariffs.active()
        return (row.id, to_spec(row)) if row else None

    def _require(self, tariff_id: int) -> Tariff:
        row = self._tariffs.get(tariff_id)
        if row is None:
            raise NotFoundError(f"Tariff {tariff_id} does not exist.")
        return row


def _validated(data: TariffInput) -> TariffSpec:
    spec = data.to_spec()
    errors = validate_tariff(spec)
    if errors:
        raise ValidationFailedError("Some tariff values are inconsistent.", errors)
    return spec


def _to_read(row: Tariff) -> TariffRead:
    return TariffRead.build(row.id, row.is_active, to_spec(row))
