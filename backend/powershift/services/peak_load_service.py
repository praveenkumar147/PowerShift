"""Peak load use case: load appliances and the household limit, analyse, explain."""

from __future__ import annotations

from sqlalchemy.orm import Session

from powershift.calculation.peak_load import (
    HEAVY_APPLIANCE_KW,
    HIGH_DEMAND_FRACTION,
    DayAnalysis,
    Episode,
    Window,
    analyse_day,
    build_demands,
    summarise_week,
    worst_weekday,
)
from powershift.db.repositories.appliances import ApplianceRepository, to_spec
from powershift.db.repositories.household import HouseholdRepository
from powershift.schemas.peak_load import (
    ApplianceInfo,
    ApplianceRef,
    Contributor,
    DaySummaryRead,
    EpisodeRead,
    PeakLoadAnalysis,
    StepRead,
    WindowRead,
    kw_out,
)

NOTE_KW = (
    "Demand is power in kW (how hard the connection is pushed at one moment), not energy in kWh."
)
NOTE_WORST = (
    "Worst case assumes every appliance that is on draws its full rated power at the same moment; "
    "expected demand uses duty cycles."
)
NOTE_ESTIMATE = (
    "Estimates from your appliance settings; flexible appliances are at their usual start time."
)
NOTE_NO_LIMIT = "No household load limit is set, so limit warnings are not checked."
NOTE_HIGH = (
    f"High demand = at least {HIGH_DEMAND_FRACTION:.0%} of the load limit "
    "(or of the day's peak without a limit)."
)
NOTE_HEAVY = (
    f"Overlaps list appliances of {HEAVY_APPLIANCE_KW:g} kW or more running at the same time."
)


class PeakLoadService:
    def __init__(self, session: Session) -> None:
        rows = ApplianceRepository(session).list()
        household = HouseholdRepository(session).get()
        self._limit = household.max_load_kw if household else None
        self._demands = build_demands([(row.id, to_spec(row)) for row in rows])

    def analysis(self, weekday: int | None) -> PeakLoadAnalysis:
        week = summarise_week(self._demands, self._limit)
        chosen = weekday if weekday is not None else worst_weekday(week)
        day = analyse_day(self._demands, chosen, self._limit)
        notes = [NOTE_KW, NOTE_WORST, NOTE_ESTIMATE, NOTE_HIGH, NOTE_HEAVY]
        if self._limit is None:
            notes.insert(2, NOTE_NO_LIMIT)
        return PeakLoadAnalysis(
            weekday=chosen,
            selected_automatically=weekday is None,
            load_limit_kw=self._limit,
            peak_kw=kw_out(day.peak_kw),
            peak_expected_kw=kw_out(day.peak_expected_kw),
            headroom_kw=kw_out(self._limit - day.peak_kw) if self._limit is not None else None,
            minutes_over_limit=day.minutes_over_limit,
            peak_windows=[_window(w) for w in day.peak_windows],
            peak_fixed_kw=kw_out(day.peak_step.fixed_kw),
            peak_flexible_kw=kw_out(day.peak_step.flexible_kw),
            peak_contributors=_contributors(day),
            steps=[
                StepRead(
                    start_minute=s.start_minute,
                    worst_kw=kw_out(s.worst_kw),
                    expected_kw=kw_out(s.expected_kw),
                    fixed_kw=kw_out(s.fixed_kw),
                    flexible_kw=kw_out(s.flexible_kw),
                    appliance_ids=[d.appliance_id for d in s.running],
                )
                for s in day.steps
            ],
            violations=[_episode(e) for e in day.violations],
            high_demand=[_episode(e) for e in day.high_demand],
            overlaps=[_episode(e) for e in day.overlaps],
            conflicts=[_episode(e) for e in day.conflicts],
            week=[
                DaySummaryRead(
                    weekday=s.weekday,
                    peak_kw=kw_out(s.peak_kw),
                    peak_expected_kw=kw_out(s.peak_expected_kw),
                    peak_start_minute=s.peak_start_minute,
                    minutes_over_limit=s.minutes_over_limit,
                )
                for s in week
            ],
            appliances=[
                ApplianceInfo(
                    appliance_id=d.appliance_id,
                    name=d.name,
                    category=d.category,
                    mode=d.mode,
                    max_kw=kw_out(d.max_kw),
                    allow_simultaneous=d.allow_simultaneous,
                )
                for d in sorted(self._demands, key=lambda d: (-d.max_kw, d.name.lower()))
            ],
            notes=notes,
        )


def _window(window: Window) -> WindowRead:
    return WindowRead(
        start_minute=window.start_minute, end_minute=window.end_minute, minutes=window.minutes
    )


def _episode(episode: Episode) -> EpisodeRead:
    return EpisodeRead(
        start_minute=episode.window.start_minute,
        end_minute=episode.window.end_minute,
        minutes=episode.window.minutes,
        max_kw=kw_out(episode.max_kw),
        appliances=[
            ApplianceRef(appliance_id=d.appliance_id, name=d.name) for d in episode.appliances
        ],
    )


def _contributors(day: DayAnalysis) -> list[Contributor]:
    if not day.peak_windows:
        return []
    return [
        Contributor(appliance_id=d.appliance_id, name=d.name, mode=d.mode, kw=kw_out(d.max_kw))
        for d in day.peak_step.running
    ]
