"""Appliance use cases: validate, persist, and attach estimates and warnings."""

from __future__ import annotations

from sqlalchemy.orm import Session

from powershift.calculation.appliance_energy import estimate_appliance
from powershift.core.errors import ConflictError, NotFoundError, ValidationFailedError
from powershift.db.models import Appliance
from powershift.db.repositories.appliances import ApplianceRepository, apply_spec, to_spec
from powershift.db.repositories.household import HouseholdRepository
from powershift.domain.appliance import (
    ApplianceCategory,
    ApplianceMode,
    ApplianceSpec,
    validate_appliance,
)
from powershift.domain.household import HouseholdProfile
from powershift.schemas.appliance import ApplianceInput, ApplianceRead


class ApplianceService:
    def __init__(self, session: Session) -> None:
        self._appliances = ApplianceRepository(session)
        self._households = HouseholdRepository(session)

    def list(
        self,
        search: str | None,
        category: ApplianceCategory | None,
        mode: ApplianceMode | None,
    ) -> list[ApplianceRead]:
        household = self._households.get()
        rows = self._appliances.list(search, category, mode)
        return [_to_read(row, household) for row in rows]

    def get(self, appliance_id: int) -> ApplianceRead:
        return _to_read(self._require(appliance_id), self._households.get())

    def create(self, data: ApplianceInput) -> ApplianceRead:
        spec = self._validated_spec(data, exclude_id=None)
        row = self._appliances.add(spec)
        return _to_read(row, self._households.get())

    def update(self, appliance_id: int, data: ApplianceInput) -> ApplianceRead:
        row = self._require(appliance_id)
        spec = self._validated_spec(data, exclude_id=appliance_id)
        apply_spec(row, spec)
        return _to_read(row, self._households.get())

    def delete(self, appliance_id: int) -> None:
        self._appliances.delete(self._require(appliance_id))

    def _require(self, appliance_id: int) -> Appliance:
        row = self._appliances.get(appliance_id)
        if row is None:
            raise NotFoundError(f"Appliance {appliance_id} does not exist.")
        return row

    def _validated_spec(self, data: ApplianceInput, exclude_id: int | None) -> ApplianceSpec:
        spec = data.to_spec()
        errors = validate_appliance(spec)
        if errors:
            raise ValidationFailedError("Some values are inconsistent.", errors)
        if self._appliances.name_taken(spec.name, exclude_id):
            raise ConflictError(
                f'An appliance named "{spec.name}" already exists.',
                {"name": "This name is already used by another appliance."},
            )
        return spec


def appliance_warnings(spec: ApplianceSpec, household: HouseholdProfile | None) -> list[str]:
    """Problems that don't block saving but the user should see."""
    warnings: list[str] = []
    max_kw = estimate_appliance(spec).max_power_kw
    if household is not None and max_kw > household.max_load_kw:
        warnings.append(
            f"At full power this appliance draws {max_kw:.2f} kW, more than the household "
            f"load limit of {household.max_load_kw:.2f} kW."
        )
    return warnings


def _to_read(row: Appliance, household: HouseholdProfile | None) -> ApplianceRead:
    spec = to_spec(row)
    return ApplianceRead.build(
        row.id, spec, estimate_appliance(spec), appliance_warnings(spec, household)
    )
