"""Request/response models for appliances.

Pydantic checks each field on its own (type, range, 15-minute steps). Rules that
involve several fields are checked in powershift.domain.appliance.
"""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from powershift.calculation.appliance_energy import ApplianceEstimate
from powershift.domain.appliance import (
    ApplianceCategory,
    ApplianceMode,
    ApplianceSpec,
    FlexibleSchedule,
    Priority,
)
from powershift.domain.time_window import MINUTES_PER_DAY, TIME_STEP_MINUTES, TimeWindow

MAX_RATED_POWER_W = 100_000  # 100 kW: far above any household appliance; catches typos
MAX_QUANTITY = 100
MAX_FIXED_BLOCKS = 24

StartMinute = Annotated[int, Field(ge=0, le=MINUTES_PER_DAY - 1, multiple_of=TIME_STEP_MINUTES)]
EndMinute = Annotated[int, Field(ge=1, le=MINUTES_PER_DAY, multiple_of=TIME_STEP_MINUTES)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class TimeBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_minute: StartMinute
    end_minute: EndMinute

    def to_window(self) -> TimeWindow:
        return TimeWindow(self.start_minute, self.end_minute)

    @classmethod
    def from_window(cls, window: TimeWindow) -> TimeBlock:
        return cls(start_minute=window.start_minute, end_minute=window.end_minute)


class FlexibleSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_duration_minutes: int = Field(
        ge=TIME_STEP_MINUTES, le=MINUTES_PER_DAY, multiple_of=TIME_STEP_MINUTES
    )
    earliest_start_minute: StartMinute
    latest_end_minute: EndMinute
    current_start_minute: StartMinute
    preferred_start_minute: StartMinute | None = None
    preferred_end_minute: EndMinute | None = None
    must_be_contiguous: bool = True

    @model_validator(mode="after")
    def preferred_both_or_neither(self) -> Self:
        if (self.preferred_start_minute is None) != (self.preferred_end_minute is None):
            raise ValueError("Set both preferred start and end, or leave both empty.")
        return self

    def to_schedule(self) -> FlexibleSchedule:
        preferred = None
        if self.preferred_start_minute is not None and self.preferred_end_minute is not None:
            preferred = TimeWindow(self.preferred_start_minute, self.preferred_end_minute)
        return FlexibleSchedule(
            run_duration_minutes=self.run_duration_minutes,
            allowed_window=TimeWindow(self.earliest_start_minute, self.latest_end_minute),
            current_start_minute=self.current_start_minute,
            preferred_window=preferred,
            must_be_contiguous=self.must_be_contiguous,
        )

    @classmethod
    def from_schedule(cls, flex: FlexibleSchedule) -> FlexibleSettings:
        preferred = flex.preferred_window
        return cls(
            run_duration_minutes=flex.run_duration_minutes,
            earliest_start_minute=flex.allowed_window.start_minute,
            latest_end_minute=flex.allowed_window.end_minute,
            current_start_minute=flex.current_start_minute,
            preferred_start_minute=preferred.start_minute if preferred else None,
            preferred_end_minute=preferred.end_minute if preferred else None,
            must_be_contiguous=flex.must_be_contiguous,
        )


class ApplianceInput(BaseModel):
    """Body of POST /api/appliances and PUT /api/appliances/{id}."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    category: ApplianceCategory
    rated_power_w: float = Field(gt=0, le=MAX_RATED_POWER_W)
    quantity: int = Field(ge=1, le=MAX_QUANTITY)
    duty_cycle: float = Field(gt=0, le=1)
    mode: ApplianceMode
    priority: Priority = Priority.MEDIUM
    allow_simultaneous: bool = True
    operating_days: list[Annotated[int, Field(ge=0, le=6)]] = Field(min_length=1, max_length=7)
    fixed_blocks: list[TimeBlock] = Field(default_factory=list, max_length=MAX_FIXED_BLOCKS)
    flexible: FlexibleSettings | None = None

    @field_validator("operating_days")
    @classmethod
    def unique_sorted_days(cls, days: list[int]) -> list[int]:
        if len(set(days)) != len(days):
            raise ValueError("Each weekday may appear only once.")
        return sorted(days)

    def to_spec(self) -> ApplianceSpec:
        return ApplianceSpec(
            name=self.name,
            category=self.category,
            rated_power_w=self.rated_power_w,
            quantity=self.quantity,
            duty_cycle=self.duty_cycle,
            mode=self.mode,
            priority=self.priority,
            allow_simultaneous=self.allow_simultaneous,
            operating_days=tuple(self.operating_days),
            fixed_blocks=tuple(block.to_window() for block in self.fixed_blocks),
            flexible=self.flexible.to_schedule() if self.flexible else None,
        )


class EstimateRead(BaseModel):
    max_power_kw: float
    average_power_kw: float
    on_hours_per_day: float
    energy_per_operating_day_kwh: float
    energy_per_week_kwh: float


class ApplianceRead(ApplianceInput):
    model_config = ConfigDict(extra="ignore")

    id: int
    estimates: EstimateRead
    warnings: list[str]

    @classmethod
    def build(
        cls,
        appliance_id: int,
        spec: ApplianceSpec,
        estimate: ApplianceEstimate,
        warnings: list[str],
    ) -> ApplianceRead:
        return cls(
            id=appliance_id,
            name=spec.name,
            category=spec.category,
            rated_power_w=spec.rated_power_w,
            quantity=spec.quantity,
            duty_cycle=spec.duty_cycle,
            mode=spec.mode,
            priority=spec.priority,
            allow_simultaneous=spec.allow_simultaneous,
            operating_days=list(spec.operating_days),
            fixed_blocks=[TimeBlock.from_window(w) for w in spec.fixed_blocks],
            flexible=FlexibleSettings.from_schedule(spec.flexible) if spec.flexible else None,
            estimates=EstimateRead(
                max_power_kw=estimate.max_power_kw,
                average_power_kw=estimate.average_power_kw,
                on_hours_per_day=estimate.on_hours_per_day,
                energy_per_operating_day_kwh=estimate.energy_per_operating_day_kwh,
                energy_per_week_kwh=estimate.energy_per_week_kwh,
            ),
            warnings=warnings,
        )
