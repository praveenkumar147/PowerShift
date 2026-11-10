"""Substeps G-H: objectives, solver execution and status handling.

Objective: multi-stage (lexicographic) optimisation
---------------------------------------------------
Each stage minimises one quantity, then LOCKS its best value with a constraint
before the next stage runs, so a later goal can never make an earlier one worse.

  Lowest cost   : cost -> peak -> preferred-window misses -> movement
  Lowest peak   : peak -> cost -> preferred-window misses -> movement
  Balanced      : blend -> cost -> peak -> preferred-window misses -> movement

"movement" (minutes moved from the usual start) is last: among equally good
schedules, the one that changes the household's habits least is chosen. It also
makes the answer unique, which keeps results reproducible.

The balanced blend adds cost and peak only after dividing each by its value in
the CURRENT schedule, so both are unit-free ratios (1.0 = "same as today"):

    blend = w x cost / cost_ref  +  (1 - w) x peak / peak_ref        w = weight / 100

CP-SAT needs integers, so both sides are multiplied by 100 x cost_ref x peak_ref:

    blend_int = weight x peak_ref x cost  +  (100 - weight) x cost_ref x peak

Minimising blend_int gives exactly the same schedule as minimising blend.

Trade-off: the cheapest hours are the same for every appliance, so pure cost
minimisation tends to stack appliances there and raise the peak; pure peak
minimisation spreads them out, possibly into expensive hours. The stage order
(or the weight) is how the user chooses between the two.

Solver statuses
---------------
OPTIMAL        every stage was solved to proven optimality.
FEASIBLE       a valid schedule was found but at least one stage hit the time
               limit before proving it is the best; never reported as optimal.
INFEASIBLE     no schedule satisfies all constraints (see diagnose.py).
UNKNOWN        the time limit ran out before any schedule was found.
MODEL_INVALID  the model itself is malformed (a programming error).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum

from ortools.sat.python import cp_model

from powershift.optimization.builder import BuiltModel, build_model
from powershift.optimization.problem import (
    Priority,
    SchedulingProblem,
    baseline_starts,
    evaluate,
)

WEIGHT_SCALE = 100
MIN_STAGE_SECONDS = 0.5
"""Every stage gets at least this long, even if earlier stages used the budget."""


class SolveStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    MODEL_INVALID = "MODEL_INVALID"


@dataclass(frozen=True, slots=True)
class SolverSettings:
    time_limit_seconds: float = 10.0
    balance_weight: int = 50
    """Balanced goal only: percent of importance given to cost (0-100)."""
    random_seed: int = 1
    num_workers: int = 1
    """One worker makes the search deterministic: same input, same answer."""


@dataclass(frozen=True, slots=True)
class StageResult:
    name: str
    status: str
    value: int | None
    seconds: float


@dataclass(frozen=True, slots=True)
class SolveResult:
    status: SolveStatus
    starts: dict[int, int]
    """appliance_id -> start minute; empty unless OPTIMAL or FEASIBLE."""
    stages: tuple[StageResult, ...]
    seconds: float
    cost: int | None = None
    peak_w: int | None = None
    preferred_misses: int | None = None
    movement_minutes: int | None = None


def overall_status(stage_statuses: list[str]) -> SolveStatus:
    """Combines per-stage CP-SAT statuses into one honest overall status."""
    if not stage_statuses:
        return SolveStatus.UNKNOWN
    first = stage_statuses[0]
    if first not in ("OPTIMAL", "FEASIBLE"):
        return SolveStatus(first) if first in SolveStatus.__members__ else SolveStatus.UNKNOWN
    if all(status == "OPTIMAL" for status in stage_statuses):
        return SolveStatus.OPTIMAL
    # A schedule exists, but some stage was not proven optimal.
    return SolveStatus.FEASIBLE


def _stages(
    problem: SchedulingProblem, built: BuiltModel, priority: Priority, weight: int
) -> list[tuple[str, cp_model.LinearExprT]]:
    tie_breaks: list[tuple[str, cp_model.LinearExprT]] = [
        ("preferred_window", built.preferred_misses),
        ("movement", built.movement),
    ]
    cost: tuple[str, cp_model.LinearExprT] = ("cost", built.cost)
    peak: tuple[str, cp_model.LinearExprT] = ("peak", built.peak_w)
    if priority is Priority.COST:
        return [cost, peak, *tie_breaks]
    if priority is Priority.PEAK:
        return [peak, cost, *tie_breaks]
    reference = evaluate(problem, baseline_starts(problem))
    cost_ref = max(reference.cost, 1)
    peak_ref = max(reference.peak_w, 1)
    blend = weight * peak_ref * built.cost + (WEIGHT_SCALE - weight) * cost_ref * built.peak_w
    return [("balanced", blend), cost, peak, *tie_breaks]


def solve(problem: SchedulingProblem, priority: Priority, settings: SolverSettings) -> SolveResult:
    if not 0 <= settings.balance_weight <= WEIGHT_SCALE:
        raise ValueError("balance_weight must be between 0 and 100")
    built = build_model(problem)
    started = time.perf_counter()
    results: list[StageResult] = []
    starts: dict[int, int] = {}

    for name, expression in _stages(problem, built, priority, settings.balance_weight):
        solver = cp_model.CpSolver()
        solver.parameters.random_seed = settings.random_seed
        solver.parameters.num_workers = settings.num_workers
        remaining = settings.time_limit_seconds - (time.perf_counter() - started)
        solver.parameters.max_time_in_seconds = max(remaining, MIN_STAGE_SECONDS)

        built.model.minimize(expression)
        stage_started = time.perf_counter()
        status = solver.solve(built.model)
        status_name = solver.status_name(status)
        found = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        value = round(solver.objective_value) if found else None
        results.append(StageResult(name, status_name, value, time.perf_counter() - stage_started))
        if not found or value is None:
            break

        starts = {
            appliance_id: next(s for s, var in variables.items() if solver.value(var))
            for appliance_id, variables in built.starts.items()
        }
        # Lock this stage's result so later stages cannot undo it. If optimality
        # was not proven, later stages may still improve it, never worsen it.
        if status == cp_model.OPTIMAL:
            built.model.add(expression == value)
        else:
            built.model.add(expression <= value)
        # Start the next stage from this schedule.
        built.model.clear_hints()  # type: ignore[no-untyped-call]
        for variables in built.starts.values():
            for var in variables.values():
                built.model.add_hint(var, solver.value(var))

    outcome = overall_status([stage.status for stage in results])
    seconds = time.perf_counter() - started
    if outcome not in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE):
        return SolveResult(outcome, {}, tuple(results), seconds)
    score = evaluate(problem, starts)
    return SolveResult(
        status=outcome,
        starts=starts,
        stages=tuple(results),
        seconds=seconds,
        cost=score.cost,
        peak_w=score.peak_w,
        preferred_misses=score.preferred_misses,
        movement_minutes=score.movement_minutes,
    )
