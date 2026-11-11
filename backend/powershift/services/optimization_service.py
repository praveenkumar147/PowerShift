"""Smart Scheduler use case.

Runs the ten steps in order:
 1 validate inputs -> 2-6 build the CP-SAT model -> 7 solve -> 8 interpret the
 status -> 9 validate the schedule independently -> 10 return (and store) a
 structured result with before/after figures and explanations.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from decimal import Decimal
from functools import partial
from importlib.metadata import version as package_version

from sqlalchemy import select
from sqlalchemy.orm import Session

from powershift import __version__
from powershift.calculation.peak_load import DayAnalysis, build_demands
from powershift.calculation.tariff_engine import money
from powershift.core.errors import NotFoundError, ValidationFailedError
from powershift.db.models.optimization import OptimizationRun, OptimizationRunItem
from powershift.db.repositories.appliances import ApplianceRepository, to_spec
from powershift.db.repositories.household import HouseholdRepository
from powershift.domain.household import TimeFormat
from powershift.domain.tariff import TariffType
from powershift.domain.time_window import format_minute
from powershift.optimization.metrics import ScheduleMetrics
from powershift.optimization.pipeline import run_pipeline
from powershift.optimization.problem import (
    WATTS_PER_KW,
    Priority,
)
from powershift.optimization.runner import SolverSettings, SolveStatus
from powershift.schemas.energy import TariffSummary
from powershift.schemas.optimization import (
    CheckRead,
    DiagnosticRead,
    MetricsRead,
    OptimizationRequest,
    OptimizationRunRead,
    OptimizationSummary,
    ProfileComparison,
    ReasonRead,
    ScheduleItem,
    StageRead,
)
from powershift.schemas.peak_load import ApplianceInfo, StepRead, kw_out
from powershift.services.tariff_service import TariffService

HISTORY_LIMIT = 50

NOTE_ESTIMATE = (
    "Estimates from your appliance settings, not measured consumption. "
    "Savings are estimated, not guaranteed."
)
NOTE_ONE_START = "Each flexible appliance gets one start time, used on every day it runs."
NOTE_NOT_TOU = (
    "Your active tariff is not time-of-use, so moving appliances does not change the bill; "
    "the scheduler can only reduce peak demand and resolve conflicts."
)
NOTE_NO_TARIFF = "No active tariff: costs are not calculated, only peak demand is optimised."
NOTE_BASELINE_LIMIT = "Your current schedule exceeds the load limit for {minutes} minutes per week."
NOTE_BASELINE_CONFLICT = (
    "In your current schedule, appliances marked 'not at the same time' overlap "
    "for {minutes} minutes per week."
)
NOTE_FEASIBLE = (
    "The time limit was reached before the solver could prove this is the best possible "
    "schedule. It is valid, but a better one may exist; try a longer time limit."
)


def _money(value: Decimal | None) -> float | None:
    return None if value is None else float(money(value))


def _metrics(m: ScheduleMetrics) -> MetricsRead:
    return MetricsRead(
        weekly_energy_charge=_money(m.weekly_energy_charge),
        monthly_bill=_money(m.monthly_bill),
        peak_kw=kw_out(m.peak_kw),
        peak_expected_kw=kw_out(m.peak_expected_kw),
        peak_weekday=m.peak_weekday,
        minutes_over_limit=m.minutes_over_limit,
        conflict_minutes=m.conflict_minutes,
    )


def _steps(day: DayAnalysis) -> list[StepRead]:
    return [
        StepRead(
            start_minute=s.start_minute,
            worst_kw=kw_out(s.worst_kw),
            expected_kw=kw_out(s.expected_kw),
            fixed_kw=kw_out(s.fixed_kw),
            flexible_kw=kw_out(s.flexible_kw),
            appliance_ids=[d.appliance_id for d in s.running],
        )
        for s in day.steps
    ]


class OptimizationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def run(self, request: OptimizationRequest, today: date) -> OptimizationRunRead:
        appliances = [(row.id, to_spec(row)) for row in ApplianceRepository(self._session).list()]
        household = HouseholdRepository(self._session).get()
        limit_kw = household.max_load_kw if household else None
        active = TariffService(self._session).active_spec()
        tariff_id, tariff = active if active else (None, None)
        fmt = partial(
            format_minute, twelve_hour=bool(household and household.time_format is TimeFormat.H12)
        )

        # 1-9. Validate inputs, build and solve the CP-SAT model, interpret the status,
        # validate the schedule independently, explain or diagnose (shared pipeline).
        year, month = today.year, today.month
        settings = SolverSettings(
            time_limit_seconds=request.time_limit_seconds, balance_weight=request.balance_weight
        )
        outcome = run_pipeline(
            appliances,
            tariff,
            limit_kw,
            request.priority,
            settings,
            request.start_step_minutes,
            year,
            month,
            fmt,
        )
        if outcome.issues:
            raise ValidationFailedError(
                " ".join(issue.message for issue in outcome.issues),
                {
                    ("priority" if i.code == "no_tariff" else "appliances"): i.message
                    for i in outcome.issues
                },
            )
        assert outcome.result is not None  # set whenever there are no input issues
        result = outcome.result
        baseline = outcome.before
        optimized = outcome.optimized
        found = outcome.found
        proven = outcome.proven_optimal
        checks = [CheckRead(**dataclasses.asdict(check)) for check in outcome.checks]
        diagnostics = [DiagnosticRead(code=d.code, message=d.message) for d in outcome.diagnostics]
        items: list[ScheduleItem] = []
        profile: ProfileComparison | None = None
        if found and optimized is not None:
            items = [
                ScheduleItem(
                    appliance_id=task.appliance_id,
                    name=task.name,
                    power_kw=kw_out(task.power_w / WATTS_PER_KW),
                    duration_minutes=task.duration_minutes,
                    baseline_start_minute=task.current_start_minute,
                    start_minute=outcome.schedule[task.appliance_id].start_minute,
                    end_minute=outcome.schedule[task.appliance_id].end_minute,
                    moved=outcome.schedule[task.appliance_id].start_minute
                    != task.current_start_minute,
                    reasons=[
                        ReasonRead(code=r.code, text=r.text)
                        for r in outcome.reasons[task.appliance_id]
                    ],
                )
                for task in outcome.problem.tasks
            ]
            weekday = baseline.peak_weekday
            profile = ProfileComparison(
                weekday=weekday,
                before=_steps(baseline.days[weekday]),
                after=_steps(optimized.days[weekday]),
            )

        schedule_valid = found and all(check.passed for check in checks)
        notes = [NOTE_ESTIMATE, NOTE_ONE_START]
        if tariff is None:
            notes.append(NOTE_NO_TARIFF)
        elif tariff.tariff_type is not TariffType.TOU:
            notes.append(NOTE_NOT_TOU)
        if baseline.minutes_over_limit:
            notes.append(NOTE_BASELINE_LIMIT.format(minutes=baseline.minutes_over_limit))
        if baseline.conflict_minutes:
            notes.append(NOTE_BASELINE_CONFLICT.format(minutes=baseline.conflict_minutes))
        if result.status is SolveStatus.FEASIBLE:
            notes.append(NOTE_FEASIBLE)

        savings = None
        if optimized and baseline.monthly_bill is not None and optimized.monthly_bill is not None:
            savings = _money(baseline.monthly_bill - optimized.monthly_bill)

        # 10. Store and return.
        row = OptimizationRun(
            priority=request.priority.value,
            balance_weight=request.balance_weight,
            start_step_minutes=request.start_step_minutes,
            time_limit_seconds=request.time_limit_seconds,
            random_seed=settings.random_seed,
            app_version=__version__,
            solver_version=f"OR-Tools CP-SAT {package_version('ortools')}",
            status=result.status.value,
            schedule_valid=schedule_valid,
            solve_time_ms=round(result.seconds * 1000),
            moved_count=sum(item.moved for item in items),
            baseline_bill=money(baseline.monthly_bill)
            if baseline.monthly_bill is not None
            else None,
            optimized_bill=money(optimized.monthly_bill)
            if optimized and optimized.monthly_bill is not None
            else None,
            baseline_peak_kw=kw_out(baseline.peak_kw),
            optimized_peak_kw=kw_out(optimized.peak_kw) if optimized else None,
            inputs_json=json.dumps(
                {
                    "appliances": [{"id": i, **dataclasses.asdict(spec)} for i, spec in appliances],
                    "tariff": dataclasses.asdict(tariff) if tariff else None,
                    "load_limit_kw": limit_kw,
                    "bill_month": [year, month],
                },
                default=str,
            ),
            result_json="{}",
            items=[
                OptimizationRunItem(
                    appliance_id=item.appliance_id,
                    appliance_name=item.name,
                    baseline_start_minute=item.baseline_start_minute,
                    start_minute=item.start_minute,
                    end_minute=item.end_minute,
                )
                for item in items
            ],
        )
        self._session.add(row)
        self._session.flush()

        response = OptimizationRunRead(
            id=row.id,
            created_at=row.created_at,
            priority=request.priority,
            balance_weight=request.balance_weight,
            start_step_minutes=request.start_step_minutes,
            time_limit_seconds=request.time_limit_seconds,
            random_seed=settings.random_seed,
            solver=row.solver_version,
            status=result.status,
            proven_optimal=proven,
            schedule_valid=schedule_valid,
            solve_time_ms=row.solve_time_ms,
            stages=[StageRead(**dataclasses.asdict(stage)) for stage in result.stages],
            load_limit_kw=limit_kw,
            tariff=TariffSummary(id=tariff_id, name=tariff.name, tariff_type=tariff.tariff_type)
            if tariff and tariff_id is not None
            else None,
            bill_year=year,
            bill_month=month,
            baseline=_metrics(baseline),
            optimized=_metrics(optimized) if optimized else None,
            monthly_savings=savings,
            peak_reduction_kw=kw_out(baseline.peak_kw - optimized.peak_kw) if optimized else None,
            items=items,
            validation=checks,
            diagnostics=diagnostics,
            profile=profile,
            appliances=[
                ApplianceInfo(
                    appliance_id=d.appliance_id,
                    name=d.name,
                    category=d.category,
                    mode=d.mode,
                    max_kw=kw_out(d.max_kw),
                    allow_simultaneous=d.allow_simultaneous,
                )
                for d in build_demands(appliances)
            ],
            notes=notes,
        )
        row.result_json = response.model_dump_json()
        return response

    def history(self) -> list[OptimizationSummary]:
        rows = self._session.scalars(
            select(OptimizationRun).order_by(OptimizationRun.id.desc()).limit(HISTORY_LIMIT)
        )
        return [
            OptimizationSummary(
                id=row.id,
                created_at=row.created_at,
                priority=Priority(row.priority),
                status=SolveStatus(row.status),
                schedule_valid=row.schedule_valid,
                solve_time_ms=row.solve_time_ms,
                moved_count=row.moved_count,
                baseline_bill=_money(row.baseline_bill),
                optimized_bill=_money(row.optimized_bill),
                baseline_peak_kw=row.baseline_peak_kw,
                optimized_peak_kw=row.optimized_peak_kw,
            )
            for row in rows
        ]

    def get(self, run_id: int) -> OptimizationRunRead:
        row = self._session.get(OptimizationRun, run_id)
        if row is None:
            raise NotFoundError(f"Optimization run {run_id} does not exist.")
        return OptimizationRunRead.model_validate_json(row.result_json)
