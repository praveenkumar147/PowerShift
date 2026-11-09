"""Response model for peak load analysis. All power values are kW (not kWh)."""

from __future__ import annotations

from pydantic import BaseModel

from powershift.domain.appliance import ApplianceCategory, ApplianceMode

KW_DECIMALS = 3


def kw_out(value: float) -> float:
    return round(value, KW_DECIMALS)


class ApplianceRef(BaseModel):
    appliance_id: int
    name: str


class ApplianceInfo(ApplianceRef):
    category: ApplianceCategory
    mode: ApplianceMode
    max_kw: float
    allow_simultaneous: bool


class Contributor(ApplianceRef):
    mode: ApplianceMode
    kw: float


class WindowRead(BaseModel):
    start_minute: int
    end_minute: int
    """May be <= start_minute when the window runs past midnight; 1440 = midnight."""
    minutes: int


class EpisodeRead(WindowRead):
    max_kw: float
    appliances: list[ApplianceRef]


class StepRead(BaseModel):
    start_minute: int
    worst_kw: float
    expected_kw: float
    fixed_kw: float
    flexible_kw: float
    appliance_ids: list[int]


class DaySummaryRead(BaseModel):
    weekday: int
    peak_kw: float
    peak_expected_kw: float
    peak_start_minute: int
    minutes_over_limit: int


class PeakLoadAnalysis(BaseModel):
    weekday: int
    selected_automatically: bool
    """True when no weekday was requested and the day with the highest peak was chosen."""
    load_limit_kw: float | None
    peak_kw: float
    peak_expected_kw: float
    headroom_kw: float | None
    """Load limit minus worst-case peak; negative when the limit is exceeded."""
    minutes_over_limit: int
    peak_windows: list[WindowRead]
    peak_fixed_kw: float
    peak_flexible_kw: float
    peak_contributors: list[Contributor]
    steps: list[StepRead]
    violations: list[EpisodeRead]
    high_demand: list[EpisodeRead]
    overlaps: list[EpisodeRead]
    conflicts: list[EpisodeRead]
    week: list[DaySummaryRead]
    appliances: list[ApplianceInfo]
    notes: list[str]
