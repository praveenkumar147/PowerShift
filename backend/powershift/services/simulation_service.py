"""Simulation Lab use cases.

Isolation: a scenario is stored as a list of changes. Running it reads the real
household, builds modified COPIES in memory, analyses the copies, and writes only
to the simulation tables. No appliance, tariff or household row is ever written.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import partial

from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from powershift.calculation.tariff_engine import money
from powershift.core.errors import ConflictError, NotFoundError, ValidationFailedError
from powershift.db.base import utc_now
from powershift.db.models.simulation import SimulationResult, SimulationScenario
from powershift.db.repositories.appliances import ApplianceRepository, to_spec
from powershift.db.repositories.household import HouseholdRepository
from powershift.db.repositories.tariffs import TariffRepository
from powershift.db.repositories.tariffs import to_spec as tariff_to_spec
from powershift.domain.household import TimeFormat
from powershift.domain.tariff import TariffSpec, TariffType
from powershift.domain.time_window import format_minute
from powershift.optimization.metrics import ScheduleMetrics
from powershift.optimization.pipeline import PipelineOutcome, run_pipeline
from powershift.optimization.problem import WATTS_PER_KW, Priority
from powershift.optimization.runner import SolverSettings, SolveStatus
from powershift.schemas.energy import TariffSummary
from powershift.schemas.optimization import CheckRead, DiagnosticRead, ReasonRead, ScheduleItem
from powershift.schemas.peak_load import kw_out
from powershift.schemas.simulation import (
    ChangeSchema,
    ScenarioInput,
    ScenarioRead,
    SimMetrics,
    SimulationResultRead,
)
from powershift.services.tariff_service import TariffService
from powershift.simulation.describe import describe_change
from powershift.simulation.scenario import Change, ScenarioInputs, apply_changes

SIMULATION_TIME_LIMIT_SECONDS = 10.0
START_STEP_MINUTES = 60
RESULTS_LIMIT = 20
KWH_DECIMALS = 3

CHANGES = TypeAdapter(list[ChangeSchema])

NOTE_ISOLATED = (
    "Calculated on a copy of your data. "
    "Your real appliances, tariffs and household were not changed."
)
NOTE_ESTIMATE = (
    "Estimates from your appliance settings, not measured consumption. "
    "Results reflect your household at the time of the run; run again after changing it."
)
NOTE_NO_TARIFF = "No tariff in this scenario: costs are not calculated."
NOTE_NOT_TOU = (
    "This scenario's tariff is not time-of-use, so moving appliances does not change the bill; "
    "scheduling can only reduce peak demand and resolve conflicts."
)
NOTE_FEASIBLE = (
    "The time limit was reached before the best schedule could be proven; "
    "this schedule is valid but a better one may exist."
)
NOTE_INVALID = "The solver's schedule failed independent validation, so it is not used."


def _as_utc(moment: datetime) -> datetime:
    """SQLite returns timestamps without a timezone; they are stored in UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _money(value: Decimal | None) -> float | None:
    return None if value is None else float(money(value))


def _round_diff(a: Decimal | None, b: Decimal | None) -> float | None:
    return None if a is None or b is None else float(money(a - b))


def _metrics(m: ScheduleMetrics) -> SimMetrics:
    return SimMetrics(
        monthly_kwh=round(m.monthly_kwh, KWH_DECIMALS),
        monthly_bill=_money(m.monthly_bill),
        peak_kw=kw_out(m.peak_kw),
        peak_expected_kw=kw_out(m.peak_expected_kw),
        minutes_over_limit=m.minutes_over_limit,
        conflict_minutes=m.conflict_minutes,
    )


class SimulationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._appliance_rows = ApplianceRepository(session).list()
        self._appliances = [(row.id, to_spec(row)) for row in self._appliance_rows]
        household = HouseholdRepository(session).get()
        self._household = household
        self._limit = household.max_load_kw if household else None
        self._tariffs = TariffRepository(session)

    # --- Scenarios ------------------------------------------------------------------

    def list_scenarios(self) -> list[ScenarioRead]:
        rows = self._session.scalars(
            select(SimulationScenario).order_by(func.lower(SimulationScenario.name))
        )
        return [self._to_read(row) for row in rows]

    def get(self, scenario_id: int) -> ScenarioRead:
        return self._to_read(self._require(scenario_id))

    def create(self, data: ScenarioInput) -> ScenarioRead:
        self._validate(data, exclude_id=None)
        row = SimulationScenario()
        self._apply(row, data)
        self._session.add(row)
        self._session.flush()
        return self._to_read(row)

    def update(self, scenario_id: int, data: ScenarioInput) -> ScenarioRead:
        row = self._require(scenario_id)
        self._validate(data, exclude_id=scenario_id)
        self._apply(row, data)
        self._session.flush()
        return self._to_read(row)

    def delete(self, scenario_id: int) -> None:
        self._session.delete(self._require(scenario_id))

    def results(self, scenario_id: int) -> list[SimulationResultRead]:
        self._require(scenario_id)
        rows = self._session.scalars(
            select(SimulationResult)
            .where(SimulationResult.scenario_id == scenario_id)
            .order_by(SimulationResult.id.desc())
            .limit(RESULTS_LIMIT)
        )
        return [SimulationResultRead.model_validate_json(row.result_json) for row in rows]

    # --- Running ----------------------------------------------------------------------

    def run(self, scenario_id: int, today: date) -> SimulationResultRead:
        scenario = self._require(scenario_id)
        changes = self._domain_changes(scenario)
        inputs, errors = apply_changes(self._appliances, self._limit, changes)
        scenario_tariff_id, scenario_tariff = self._scenario_tariff(inputs, errors)
        if errors:
            raise ValidationFailedError(
                "This scenario can no longer be applied to your current household.", errors
            )
        priority = Priority(scenario.priority)
        year, month = today.year, today.month
        fmt = partial(
            format_minute,
            twelve_hour=bool(self._household and self._household.time_format is TimeFormat.H12),
        )

        # The actual household, untouched: the baseline everything is compared with.
        active = TariffService(self._session).active_spec()
        base_tariff = active[1] if active else None
        base = run_pipeline(
            self._appliances,
            base_tariff,
            self._limit,
            priority,
            SolverSettings(time_limit_seconds=1),
            START_STEP_MINUTES,
            year,
            month,
            fmt,
        ).before
        # The scenario household, on copies.
        settings = SolverSettings(
            time_limit_seconds=SIMULATION_TIME_LIMIT_SECONDS, balance_weight=scenario.balance_weight
        )
        outcome = run_pipeline(
            inputs.appliances,
            scenario_tariff,
            inputs.load_limit_kw,
            priority,
            settings,
            START_STEP_MINUTES,
            year,
            month,
            fmt,
        )

        usable = outcome.valid and outcome.optimized is not None
        optimized = outcome.optimized if usable else None
        status = outcome.result.status if outcome.result else None
        items = self._items(outcome) if usable else []
        note = self._optimization_note(outcome, status)
        notes = self._notes(scenario_tariff, outcome.before, status, outcome.found and not usable)

        before = outcome.before
        result = SimulationResultRead(
            id=0,
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            created_at=utc_now(),
            priority=priority,
            balance_weight=scenario.balance_weight,
            change_descriptions=self._descriptions(changes),
            tariff=self._tariff_summary(scenario_tariff_id, scenario_tariff),
            load_limit_kw=inputs.load_limit_kw,
            bill_year=year,
            bill_month=month,
            baseline=_metrics(base),
            scenario=_metrics(before),
            optimized=_metrics(optimized) if optimized else None,
            status=status,
            proven_optimal=outcome.proven_optimal and usable,
            schedule_valid=usable,
            solve_time_ms=round(outcome.result.seconds * 1000) if outcome.result else 0,
            optimization_note=note,
            kwh_change=round(before.monthly_kwh - base.monthly_kwh, KWH_DECIMALS),
            bill_change=_round_diff(before.monthly_bill, base.monthly_bill),
            optimized_bill_change=_round_diff(
                optimized.monthly_bill if optimized else None, base.monthly_bill
            ),
            optimization_savings=_round_diff(
                before.monthly_bill, optimized.monthly_bill if optimized else None
            ),
            peak_change_kw=kw_out((optimized or before).peak_kw - base.peak_kw),
            items=items,
            validation=[CheckRead(**dataclasses.asdict(c)) for c in outcome.checks],
            diagnostics=[
                DiagnosticRead(code=d.code, message=d.message) for d in outcome.diagnostics
            ],
            notes=notes,
        )

        row = SimulationResult(
            scenario_id=scenario.id,
            status=status.value if status else None,
            schedule_valid=usable,
            baseline_kwh=base.monthly_kwh,
            scenario_kwh=before.monthly_kwh,
            baseline_bill=money(base.monthly_bill) if base.monthly_bill is not None else None,
            scenario_bill=money(before.monthly_bill) if before.monthly_bill is not None else None,
            optimized_bill=money(optimized.monthly_bill)
            if optimized and optimized.monthly_bill is not None
            else None,
            baseline_peak_kw=base.peak_kw,
            scenario_peak_kw=before.peak_kw,
            optimized_peak_kw=optimized.peak_kw if optimized else None,
            result_json="{}",
        )
        self._session.add(row)
        self._session.flush()
        result = result.model_copy(update={"id": row.id, "created_at": row.created_at})
        row.result_json = result.model_dump_json()
        return result

    # --- Helpers ------------------------------------------------------------------------

    def _require(self, scenario_id: int) -> SimulationScenario:
        row = self._session.get(SimulationScenario, scenario_id)
        if row is None:
            raise NotFoundError(f"Scenario {scenario_id} does not exist.")
        return row

    def _domain_changes(self, row: SimulationScenario) -> list[Change]:
        return [c.to_domain() for c in CHANGES.validate_json(row.changes_json)]

    def _scenario_tariff(
        self, inputs: ScenarioInputs, errors: dict[str, str]
    ) -> tuple[int | None, TariffSpec | None]:
        if inputs.tariff_id is None:
            active = TariffService(self._session).active_spec()
            return (active[0], active[1]) if active else (None, None)
        row = self._tariffs.get(inputs.tariff_id)
        if row is None:
            errors["changes"] = "A tariff chosen by this scenario no longer exists."
            return None, None
        return row.id, tariff_to_spec(row)

    def _validate(self, data: ScenarioInput, exclude_id: int | None) -> None:
        clash = select(SimulationScenario.id).where(
            func.lower(SimulationScenario.name) == data.name.lower()
        )
        if exclude_id is not None:
            clash = clash.where(SimulationScenario.id != exclude_id)
        if self._session.scalar(clash) is not None:
            raise ConflictError(
                f'A scenario named "{data.name}" already exists.',
                {"name": "This name is already used by another scenario."},
            )
        changes = [c.to_domain() for c in data.changes]
        inputs, errors = apply_changes(self._appliances, self._limit, changes)
        self._scenario_tariff(inputs, errors)
        if errors:
            raise ValidationFailedError("Some changes are inconsistent.", errors)

    def _apply(self, row: SimulationScenario, data: ScenarioInput) -> None:
        row.name = data.name
        row.description = data.description or None
        row.priority = data.priority.value
        row.balance_weight = data.balance_weight
        row.changes_json = json.dumps([c.model_dump(mode="json") for c in data.changes])

    def _descriptions(self, changes: list[Change]) -> list[str]:
        by_id = {i: spec for i, spec in self._appliances}
        tariff_names = {t.id: t.name for t in self._tariffs.list()}
        return [describe_change(c, by_id, tariff_names, self._limit) for c in changes]

    def _to_read(self, row: SimulationScenario) -> ScenarioRead:
        latest = self._session.scalars(
            select(SimulationResult)
            .where(SimulationResult.scenario_id == row.id)
            .order_by(SimulationResult.id.desc())
            .limit(1)
        ).first()
        return ScenarioRead(
            id=row.id,
            name=row.name,
            description=row.description,
            priority=Priority(row.priority),
            balance_weight=row.balance_weight,
            changes=CHANGES.validate_json(row.changes_json),
            change_descriptions=self._descriptions(self._domain_changes(row)),
            created_at=_as_utc(row.created_at),
            updated_at=_as_utc(row.updated_at),
            latest_result=SimulationResultRead.model_validate_json(latest.result_json)
            if latest
            else None,
            result_is_stale=latest is not None
            and _as_utc(row.updated_at) > _as_utc(latest.created_at),
        )

    @staticmethod
    def _tariff_summary(tariff_id: int | None, tariff: TariffSpec | None) -> TariffSummary | None:
        if tariff is None or tariff_id is None:
            return None
        return TariffSummary(id=tariff_id, name=tariff.name, tariff_type=tariff.tariff_type)

    @staticmethod
    def _items(outcome: PipelineOutcome) -> list[ScheduleItem]:
        return [
            ScheduleItem(
                appliance_id=task.appliance_id,
                name=task.name,
                power_kw=kw_out(task.power_w / WATTS_PER_KW),
                duration_minutes=task.duration_minutes,
                baseline_start_minute=task.current_start_minute,
                start_minute=outcome.schedule[task.appliance_id].start_minute,
                end_minute=outcome.schedule[task.appliance_id].end_minute,
                moved=outcome.schedule[task.appliance_id].start_minute != task.current_start_minute,
                reasons=[
                    ReasonRead(code=r.code, text=r.text) for r in outcome.reasons[task.appliance_id]
                ],
            )
            for task in outcome.problem.tasks
        ]

    @staticmethod
    def _optimization_note(outcome: PipelineOutcome, status: SolveStatus | None) -> str | None:
        if outcome.issues:
            return "Scheduling was not attempted: " + " ".join(i.message for i in outcome.issues)
        if status is SolveStatus.INFEASIBLE:
            return "No valid schedule exists for this scenario (see the reasons below)."
        if status is SolveStatus.UNKNOWN:
            return "No schedule was found within the time limit."
        if status is SolveStatus.MODEL_INVALID:
            return "Internal model error."
        if outcome.found and not outcome.valid:
            return NOTE_INVALID
        return None

    @staticmethod
    def _notes(
        tariff: TariffSpec | None,
        before: ScheduleMetrics,
        status: SolveStatus | None,
        invalid: bool,
    ) -> list[str]:
        notes = [NOTE_ISOLATED, NOTE_ESTIMATE]
        if tariff is None:
            notes.append(NOTE_NO_TARIFF)
        elif tariff.tariff_type is not TariffType.TOU:
            notes.append(NOTE_NOT_TOU)
        if before.minutes_over_limit:
            notes.append(
                f"At their usual times, this scenario's appliances exceed the load limit for "
                f"{before.minutes_over_limit} minutes per week."
            )
        if status is SolveStatus.FEASIBLE:
            notes.append(NOTE_FEASIBLE)
        if invalid:
            notes.append(NOTE_INVALID)
        return notes
