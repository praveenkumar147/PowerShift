"""Request/response models for tariffs.

Money and rates are Decimal internally and sent to the UI as JSON numbers.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
)

from powershift.domain.tariff import (
    Charge,
    ChargeKind,
    DayType,
    Slab,
    SlabMode,
    TariffSpec,
    TariffType,
    TouPeriod,
)
from powershift.domain.time_window import TimeWindow
from powershift.schemas.appliance import EndMinute, StartMinute

AsFloat = PlainSerializer(float, return_type=float, when_used="json")
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=4), AsFloat]
Kwh = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3), AsFloat]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

MAX_PERIODS = 48
MAX_SLABS = 20
MAX_CHARGES = 20
MAX_PERCENT = Decimal(100)


class TouPeriodSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_type: DayType = DayType.ALL
    start_minute: StartMinute
    end_minute: EndMinute
    rate_per_kwh: Money


class SlabSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    up_to_kwh: Kwh | None
    rate_per_kwh: Money


class ChargeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ChargeKind
    label: Label
    amount: Money

    @model_validator(mode="after")
    def percentage_at_most_100(self) -> Self:
        if self.kind is ChargeKind.PERCENTAGE and self.amount > MAX_PERCENT:
            raise ValueError("A percentage charge cannot exceed 100%.")
        return self


class TariffInput(BaseModel):
    """Body of POST /api/tariffs and PUT /api/tariffs/{id}."""

    model_config = ConfigDict(extra="forbid")

    name: Label
    tariff_type: TariffType
    effective_date: date
    flat_rate_per_kwh: Money | None = None
    tou_periods: list[TouPeriodSchema] = Field(default_factory=list, max_length=MAX_PERIODS)
    slabs: list[SlabSchema] = Field(default_factory=list, max_length=MAX_SLABS)
    slab_mode: SlabMode = SlabMode.TELESCOPIC
    charges: list[ChargeSchema] = Field(default_factory=list, max_length=MAX_CHARGES)

    def to_spec(self) -> TariffSpec:
        return TariffSpec(
            name=self.name,
            tariff_type=self.tariff_type,
            effective_date=self.effective_date,
            flat_rate_per_kwh=self.flat_rate_per_kwh,
            tou_periods=tuple(
                TouPeriod(TimeWindow(p.start_minute, p.end_minute), p.day_type, p.rate_per_kwh)
                for p in self.tou_periods
            ),
            slabs=tuple(Slab(s.up_to_kwh, s.rate_per_kwh) for s in self.slabs),
            slab_mode=self.slab_mode,
            charges=tuple(Charge(c.kind, c.label, c.amount) for c in self.charges),
        )


class TariffRead(TariffInput):
    id: int
    is_active: bool

    @classmethod
    def build(cls, tariff_id: int, is_active: bool, spec: TariffSpec) -> TariffRead:
        return cls(
            id=tariff_id,
            is_active=is_active,
            name=spec.name,
            tariff_type=spec.tariff_type,
            effective_date=spec.effective_date,
            flat_rate_per_kwh=spec.flat_rate_per_kwh,
            tou_periods=[
                TouPeriodSchema(
                    day_type=p.day_type,
                    start_minute=p.window.start_minute,
                    end_minute=p.window.end_minute,
                    rate_per_kwh=p.rate_per_kwh,
                )
                for p in spec.tou_periods
            ],
            slabs=[
                SlabSchema(up_to_kwh=s.up_to_kwh, rate_per_kwh=s.rate_per_kwh) for s in spec.slabs
            ],
            slab_mode=spec.slab_mode,
            charges=[
                ChargeSchema(kind=c.kind, label=c.label, amount=c.amount) for c in spec.charges
            ],
        )
