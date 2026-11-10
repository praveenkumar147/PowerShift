"""Request/response models for the Smart Scheduler."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from powershift.optimization.problem import Priority
from powershift.optimization.runner import SolveStatus
from powershift.schemas.energy import TariffSummary
from powershift.schemas.peak_load import ApplianceInfo, StepRead


class OptimizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: Priority = Priority.BALANCED
    balance_weight: int = Field(default=50, ge=0, le=100)
    """Balanced goal only: percent of importance given to cost."""
    start_step_minutes: Literal[15, 30, 60] = 60
    time_limit_seconds: float = Field(default=10, ge=1, le=60)


class ReasonRead(BaseModel):
    code: str
    text: str


class ScheduleItem(BaseModel):
    appliance_id: int
    name: str
    power_kw: float
    duration_minutes: int
    baseline_start_minute: int
    start_minute: int
    end_minute: int
    moved: bool
    reasons: list[ReasonRead]


class MetricsRead(BaseModel):
    weekly_energy_charge: float | None
    monthly_bill: float | None
    peak_kw: float
    peak_expected_kw: float
    peak_weekday: int
    minutes_over_limit: int
    conflict_minutes: int


class CheckRead(BaseModel):
    code: str
    label: str
    passed: bool
    detail: str


class StageRead(BaseModel):
    name: str
    status: str
    value: int | None
    seconds: float


class DiagnosticRead(BaseModel):
    code: str
    message: str


class ProfileComparison(BaseModel):
    weekday: int
    before: list[StepRead]
    after: list[StepRead]


class OptimizationRunRead(BaseModel):
    id: int
    created_at: datetime
    # Settings
    priority: Priority
    balance_weight: int
    start_step_minutes: int
    time_limit_seconds: float
    random_seed: int
    solver: str
    # Outcome
    status: SolveStatus
    proven_optimal: bool
    schedule_valid: bool
    """True only if a schedule was found AND every independent check passed."""
    solve_time_ms: int
    stages: list[StageRead]
    # Context
    load_limit_kw: float | None
    tariff: TariffSummary | None
    bill_year: int
    bill_month: int
    # Comparison (calculated by the normal engines, not by the solver)
    baseline: MetricsRead
    optimized: MetricsRead | None
    monthly_savings: float | None
    """Baseline bill - optimized bill. Negative means the new schedule costs more."""
    peak_reduction_kw: float | None
    items: list[ScheduleItem]
    validation: list[CheckRead]
    diagnostics: list[DiagnosticRead]
    profile: ProfileComparison | None
    appliances: list[ApplianceInfo]
    notes: list[str]


class OptimizationSummary(BaseModel):
    id: int
    created_at: datetime
    priority: Priority
    status: SolveStatus
    schedule_valid: bool
    solve_time_ms: int
    moved_count: int
    baseline_bill: float | None
    optimized_bill: float | None
    baseline_peak_kw: float
    optimized_peak_kw: float | None
