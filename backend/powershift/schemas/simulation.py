"""Request/response models for the Simulation Lab."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from powershift.optimization.problem import Priority
from powershift.optimization.runner import SolveStatus
from powershift.schemas.appliance import ApplianceInput
from powershift.schemas.energy import TariffSummary
from powershift.schemas.household import MAX_LOAD_KW
from powershift.schemas.optimization import CheckRead, DiagnosticRead, ScheduleItem
from powershift.simulation.scenario import (
    AddAppliance,
    Change,
    ChangeTariff,
    RemoveAppliance,
    ReplaceAppliance,
    SetLoadLimit,
)

MAX_CHANGES = 30
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class AddApplianceChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["add_appliance"]
    appliance: ApplianceInput

    def to_domain(self) -> Change:
        return AddAppliance(self.appliance.to_spec())


class ReplaceApplianceChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["replace_appliance"]
    appliance_id: int
    appliance: ApplianceInput
    """The appliance as it should be in the scenario (a full replacement)."""

    def to_domain(self) -> Change:
        return ReplaceAppliance(self.appliance_id, self.appliance.to_spec())


class RemoveApplianceChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["remove_appliance"]
    appliance_id: int

    def to_domain(self) -> Change:
        return RemoveAppliance(self.appliance_id)


class ChangeTariffChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["change_tariff"]
    tariff_id: int

    def to_domain(self) -> Change:
        return ChangeTariff(self.tariff_id)


class SetLoadLimitChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["set_load_limit"]
    max_load_kw: float = Field(gt=0, le=MAX_LOAD_KW)

    def to_domain(self) -> Change:
        return SetLoadLimit(self.max_load_kw)


ChangeSchema = Annotated[
    AddApplianceChange
    | ReplaceApplianceChange
    | RemoveApplianceChange
    | ChangeTariffChange
    | SetLoadLimitChange,
    Field(discriminator="type"),
]


class ScenarioInput(BaseModel):
    """Body of POST /api/simulations and PUT /api/simulations/{id}."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = (
        None
    )
    priority: Priority = Priority.BALANCED
    balance_weight: int = Field(default=50, ge=0, le=100)
    changes: list[ChangeSchema] = Field(default_factory=list, max_length=MAX_CHANGES)
    """May be empty: a scenario with no changes compares scheduling goals on today's data."""


class SimMetrics(BaseModel):
    monthly_kwh: float
    monthly_bill: float | None
    peak_kw: float
    peak_expected_kw: float
    minutes_over_limit: int
    conflict_minutes: int


class SimulationResultRead(BaseModel):
    id: int
    scenario_id: int
    scenario_name: str
    created_at: datetime
    priority: Priority
    balance_weight: int
    change_descriptions: list[str]
    tariff: TariffSummary | None
    """The tariff used in the scenario (the active tariff unless a change replaced it)."""
    load_limit_kw: float | None
    bill_year: int
    bill_month: int
    baseline: SimMetrics
    """Your actual household today, at its usual times. Never modified."""
    scenario: SimMetrics
    """The scenario's household at the usual times, before optimisation."""
    optimized: SimMetrics | None
    status: SolveStatus | None
    """None when optimisation was not attempted (see optimization_note)."""
    proven_optimal: bool
    schedule_valid: bool
    solve_time_ms: int
    optimization_note: str | None
    kwh_change: float
    bill_change: float | None
    """Scenario bill minus current bill (before optimisation). Positive = costs more."""
    optimized_bill_change: float | None
    """Optimised scenario bill minus current bill. Negative = saves money overall."""
    optimization_savings: float | None
    """Scenario bill minus optimised scenario bill: what scheduling alone recovers."""
    peak_change_kw: float
    items: list[ScheduleItem]
    validation: list[CheckRead]
    diagnostics: list[DiagnosticRead]
    notes: list[str]


class ScenarioRead(BaseModel):
    id: int
    name: str
    description: str | None
    priority: Priority
    balance_weight: int
    changes: list[ChangeSchema]
    change_descriptions: list[str]
    created_at: datetime
    updated_at: datetime
    latest_result: SimulationResultRead | None
    result_is_stale: bool
    """True if the scenario was edited after its latest result was produced."""
