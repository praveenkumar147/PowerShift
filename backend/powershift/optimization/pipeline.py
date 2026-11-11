"""The optimization pipeline shared by the Smart Scheduler and the Simulation Lab.

Takes a household described by plain objects (appliances, tariff, load limit) and
returns everything the solver, the independent validator and the explainer produced.
It touches no database, so a simulation can run it on a modified in-memory copy
without any risk of changing the real data.

Steps: validate inputs -> build + solve (CP-SAT) -> interpret status ->
measure before/after -> validate the schedule independently -> explain or diagnose.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

from powershift.domain.tariff import TariffSpec, TariffType
from powershift.domain.time_window import format_minute, run_window
from powershift.optimization.diagnose import Diagnostic, diagnose
from powershift.optimization.explain import Reason, explain
from powershift.optimization.metrics import Appliances, ScheduleMetrics, apply_schedule, measure
from powershift.optimization.problem import (
    COST_SCALE,
    WATTS_PER_KW,
    InputIssue,
    Priority,
    SchedulingProblem,
    build_problem,
    validate_problem,
)
from powershift.optimization.runner import SolveResult, SolverSettings, SolveStatus, solve
from powershift.optimization.validation import Check, ScheduledRun, validate_schedule

TimeFormatter = Callable[[int], str]


@dataclass(frozen=True, slots=True)
class PipelineOutcome:
    problem: SchedulingProblem
    issues: list[InputIssue]
    """Reasons solving was not attempted (no flexible appliances, cost goal without a tariff...)."""
    before: ScheduleMetrics
    """The household as given, at its usual start times."""
    result: SolveResult | None = None
    optimized: ScheduleMetrics | None = None
    schedule: dict[int, ScheduledRun] = field(default_factory=dict)
    checks: tuple[Check, ...] = ()
    reasons: dict[int, list[Reason]] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.result is not None and self.result.status in (
            SolveStatus.OPTIMAL,
            SolveStatus.FEASIBLE,
        )

    @property
    def proven_optimal(self) -> bool:
        return self.result is not None and self.result.status is SolveStatus.OPTIMAL

    @property
    def valid(self) -> bool:
        """A schedule was found AND every independent check passed."""
        return self.found and all(check.passed for check in self.checks)


def run_pipeline(
    appliances: Appliances,
    tariff: TariffSpec | None,
    limit_kw: float | None,
    priority: Priority,
    settings: SolverSettings,
    start_step_minutes: int,
    year: int,
    month: int,
    fmt: TimeFormatter = format_minute,
) -> PipelineOutcome:
    problem = build_problem(appliances, tariff, limit_kw, start_step_minutes)
    before = measure(appliances, tariff, limit_kw, year, month)
    issues = validate_problem(problem, priority)
    if issues:
        return PipelineOutcome(problem, issues, before)

    result = solve(problem, priority, settings)
    if result.status not in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE):
        diagnostics = diagnose(problem, fmt) if result.status is SolveStatus.INFEASIBLE else []
        return PipelineOutcome(problem, [], before, result, diagnostics=diagnostics)

    optimized = measure(apply_schedule(appliances, result.starts), tariff, limit_kw, year, month)
    schedule = {
        task.appliance_id: ScheduledRun(
            result.starts[task.appliance_id],
            run_window(result.starts[task.appliance_id], task.duration_minutes).end_minute,
        )
        for task in problem.tasks
    }
    priced = tariff is not None and tariff.tariff_type is not TariffType.SLAB
    report = validate_schedule(
        appliances,
        schedule,
        tariff,
        limit_kw,
        Decimal(result.cost) / COST_SCALE if priced and result.cost is not None else None,
        result.peak_w / WATTS_PER_KW if result.peak_w is not None else None,
        year,
        month,
    )
    reasons = explain(
        appliances,
        result.starts,
        tariff,
        limit_kw,
        result.status is SolveStatus.OPTIMAL,
        fmt,
    )
    return PipelineOutcome(problem, [], before, result, optimized, schedule, report.checks, reasons)
