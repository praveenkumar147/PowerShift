"""Why is there no valid schedule? Diagnostics for INFEASIBLE problems.

Three kinds of evidence, cheapest first:
1. Arithmetic on the inputs: fixed appliances alone above the limit; an
   appliance that cannot fit under the limit anywhere in its window.
2. Relaxation: re-solve with ONE constraint group switched off. If the problem
   becomes solvable, that group is what blocks it.
3. For the load limit, the smallest limit that would work (minimum possible peak).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ortools.sat.python import cp_model

from powershift.calculation.load_profile import WEEKDAYS
from powershift.calculation.peak_load import find_windows
from powershift.domain.time_window import format_minute
from powershift.optimization.builder import build_model
from powershift.optimization.problem import WATTS_PER_KW, SchedulingProblem, Task

DIAGNOSIS_SECONDS = 5.0
WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
TimeFormatter = Callable[[int], str]


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str


def _kw(watts: int) -> str:
    return f"{watts / WATTS_PER_KW:.2f} kW"


def _solve(
    problem: SchedulingProblem, *, limit: bool, apart: bool, minimise_peak: bool = False
) -> int | None:
    """Returns the peak (W) of a feasible schedule under the given switches, or None."""
    built = build_model(problem, enforce_limit=limit, enforce_not_simultaneous=apart)
    if minimise_peak:
        built.model.minimize(built.peak_w)
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.max_time_in_seconds = DIAGNOSIS_SECONDS
    status = solver.solve(built.model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return int(solver.value(built.peak_w))


def _fixed_load_over_limit(problem: SchedulingProblem, fmt: TimeFormatter) -> Diagnostic | None:
    assert problem.limit_w is not None
    limit = problem.limit_w
    over_days = [w for w in WEEKDAYS if max(problem.base_w[w]) > limit]
    if not over_days:
        return None
    worst = max(over_days, key=lambda w: max(problem.base_w[w]))
    windows = find_windows([load > limit for load in problem.base_w[worst]])
    spans = ", ".join(f"{fmt(w.start_minute)}-{fmt(w.end_minute)}" for w in windows)
    days = "every day" if len(over_days) == 7 else ", ".join(WEEKDAY_NAMES[w] for w in over_days)
    return Diagnostic(
        "fixed_load_over_limit",
        f"Fixed appliances alone exceed the {_kw(limit)} load limit ({days}; on {WEEKDAY_NAMES[worst]} "
        f"at {spans}, up to {_kw(max(problem.base_w[worst]))}). No schedule of flexible appliances can fix "
        "this: raise the limit or change the fixed appliances' hours.",
    )


def _best_peak_alone(problem: SchedulingProblem, task: Task) -> int:
    """Lowest household peak this appliance can achieve on its own (others ignored)."""
    return min(
        max(
            problem.base_w[w][step] + task.power_w
            for w in task.days
            for step in task.steps_for(start)
        )
        for start in task.candidates
    )


def diagnose(problem: SchedulingProblem, fmt: TimeFormatter = format_minute) -> list[Diagnostic]:
    """Call only for a problem the solver reported INFEASIBLE."""
    findings: list[Diagnostic] = []
    exclusive = [t.name for t in problem.tasks if not t.allow_simultaneous]
    limit = problem.limit_w

    if limit is not None:
        fixed = _fixed_load_over_limit(problem, fmt)
        if fixed:
            findings.append(fixed)
        for task in problem.tasks:
            best = _best_peak_alone(problem, task)
            if best > limit:
                findings.append(
                    Diagnostic(
                        "appliance_cannot_fit",
                        f"{task.name} ({_kw(task.power_w)}) cannot run anywhere in its window "
                        f"{fmt(task.window.start_minute)}-{fmt(task.window.end_minute)} without exceeding the "
                        f"{_kw(limit)} limit: even at the quietest time the household would reach {_kw(best)}.",
                    )
                )

    without_limit = _solve(problem, limit=False, apart=True, minimise_peak=True)
    without_apart = _solve(problem, limit=True, apart=False) if len(exclusive) > 1 else None

    if limit is not None and without_limit is not None:
        findings.append(
            Diagnostic(
                "limit_too_low",
                f"The load limit is the obstacle. The lowest peak any schedule can reach is "
                f"{_kw(without_limit)}, but the limit is {_kw(limit)}. A limit of at least "
                f"{_kw(without_limit)}, wider time windows, or fewer overlapping fixed loads would make it solvable.",
            )
        )
    if without_apart is not None:
        findings.append(
            Diagnostic(
                "not_simultaneous_blocks",
                "A schedule exists only if some of these run at the same time, which you have ruled out: "
                + ", ".join(exclusive)
                + ". Widen their time windows or allow one of them to overlap.",
            )
        )
    if without_limit is None and without_apart is None and len(exclusive) > 1:
        total = sum(t.duration_minutes for t in problem.tasks if not t.allow_simultaneous)
        findings.append(
            Diagnostic(
                "windows_too_tight",
                f"The appliances marked 'not at the same time' ({', '.join(exclusive)}) need "
                f"{total} minutes in total, one after another, and their windows do not leave room "
                f"on a {problem.start_step_minutes}-minute start grid. Widen the windows or use a finer start-time step.",
            )
        )
    if not findings:
        findings.append(
            Diagnostic(
                "unknown",
                "No schedule satisfies every constraint at once. Try a finer start-time step, wider windows, "
                "or a higher load limit.",
            )
        )
    return findings
