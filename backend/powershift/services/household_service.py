from __future__ import annotations

from sqlalchemy.orm import Session

from powershift.db.repositories.household import HouseholdRepository
from powershift.schemas.household import HouseholdInput, HouseholdRead


class HouseholdService:
    def __init__(self, session: Session) -> None:
        self._households = HouseholdRepository(session)

    def get(self) -> HouseholdRead | None:
        profile = self._households.get()
        return HouseholdRead.from_profile(profile) if profile else None

    def save(self, data: HouseholdInput) -> HouseholdRead:
        return HouseholdRead.from_profile(self._households.save(data.to_profile()))
