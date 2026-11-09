from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from powershift.domain.household import HouseholdProfile, TimeFormat

MAX_OCCUPANTS = 50
MAX_LOAD_KW = 1000  # far above residential connections; catches unit mistakes (W vs kW)


class HouseholdInput(BaseModel):
    """Body of PUT /api/household."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    occupants: int = Field(ge=1, le=MAX_OCCUPANTS)
    location_label: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None
    ) = None
    max_load_kw: float = Field(gt=0, le=MAX_LOAD_KW)
    currency_code: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    time_format: TimeFormat = TimeFormat.H24

    @field_validator("currency_code", mode="before")
    @classmethod
    def normalise_currency(cls, value: object) -> object:
        # Runs before the pattern check, so "usd " is accepted as "USD".
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("location_label")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        return value or None

    def to_profile(self) -> HouseholdProfile:
        return HouseholdProfile(
            name=self.name,
            occupants=self.occupants,
            location_label=self.location_label,
            max_load_kw=self.max_load_kw,
            currency_code=self.currency_code,
            time_format=self.time_format,
        )


class HouseholdRead(HouseholdInput):
    @classmethod
    def from_profile(cls, profile: HouseholdProfile) -> HouseholdRead:
        return cls(
            name=profile.name,
            occupants=profile.occupants,
            location_label=profile.location_label,
            max_load_kw=profile.max_load_kw,
            currency_code=profile.currency_code,
            time_format=profile.time_format,
        )
