"""Database access for the single household profile row."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from powershift.db.models import Household
from powershift.domain.household import HouseholdProfile, TimeFormat


class HouseholdRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> HouseholdProfile | None:
        row = self._row()
        return _to_profile(row) if row else None

    def save(self, profile: HouseholdProfile) -> HouseholdProfile:
        row = self._row() or Household()
        row.name = profile.name
        row.occupants = profile.occupants
        row.location_label = profile.location_label
        row.max_load_kw = profile.max_load_kw
        row.currency_code = profile.currency_code
        row.time_format = profile.time_format.value
        self._session.add(row)
        self._session.flush()
        return _to_profile(row)

    def _row(self) -> Household | None:
        return self._session.scalar(select(Household).order_by(Household.id).limit(1))


def _to_profile(row: Household) -> HouseholdProfile:
    return HouseholdProfile(
        name=row.name,
        occupants=row.occupants,
        location_label=row.location_label,
        max_load_kw=row.max_load_kw,
        currency_code=row.currency_code,
        time_format=TimeFormat(row.time_format),
    )
