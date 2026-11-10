"""Substeps B-G: build the CP-SAT model.

B. Decision variables
   start[a, s] in {0, 1}  - appliance a starts at minute s (one per candidate start).
   peak_w      integer    - highest household worst-case demand in any step of the week.

C. Appliance constraint
   sum over s of start[a, s] = 1   - every flexible appliance runs exactly once per
   operating day, so it always gets its full required duration.

D. Operating windows
   A variable exists only for starts whose WHOLE run fits the allowed window
   (see problem.candidate_starts), so a run outside its window cannot be expressed.

E. Contiguity
   A start covers the consecutive steps s, s+15, ..., s+duration-15 (wrapping past
   midnight), so every run is one uninterrupted block by construction.

F. Household constraints, for every weekday w and 15-minute step t:
   load[w, t] = base_w[w][t] + sum of power_w[a] x start[a, s] over (a, s) whose run covers t
   load[w, t] <= limit_w                            (if a load limit is set)
   peak_w     >= load[w, t]                         (defines the peak)
   sum of start[a, s] over "not simultaneous" a covering t <= 1

G. Objective terms (combined by the runner, see runner.py)
   cost       = sum cost_by_start[a][s] x start[a, s]       (weekly energy charge)
   misses     = number of runs outside their preferred window
   movement   = sum of minutes each run moved from its usual start
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ortools.sat.python import cp_model

from powershift.calculation.load_profile import WEEKDAYS
from powershift.domain.time_window import STEPS_PER_DAY
from powershift.optimization.problem import SchedulingProblem


@dataclass
class BuiltModel:
    model: cp_model.CpModel
    starts: dict[int, dict[int, cp_model.IntVar]]
    """appliance_id -> start minute -> 0/1 variable."""
    peak_w: cp_model.IntVar
    cost: cp_model.LinearExpr
    preferred_misses: cp_model.LinearExpr
    movement: cp_model.LinearExpr


def build_model(
    problem: SchedulingProblem,
    *,
    enforce_limit: bool = True,
    enforce_not_simultaneous: bool = True,
) -> BuiltModel:
    """The two `enforce_*` switches exist only for diagnostics: relaxing one
    constraint at a time shows which one makes a problem infeasible."""
    model = cp_model.CpModel()

    # B + C + D: one 0/1 variable per allowed start; exactly one chosen.
    starts: dict[int, dict[int, cp_model.IntVar]] = {}
    for task in problem.tasks:
        starts[task.appliance_id] = {
            s: model.new_bool_var(f"start_{task.appliance_id}_{s}") for s in task.candidates
        }
        model.add_exactly_one(starts[task.appliance_id].values())

    # E: which variables put load on each (weekday, step).
    covering: dict[tuple[int, int], list[tuple[int, cp_model.IntVar, bool]]] = defaultdict(list)
    for task in problem.tasks:
        for s, var in starts[task.appliance_id].items():
            for step in task.steps_for(s):
                for weekday in task.days:
                    covering[(weekday, step)].append((task.power_w, var, task.allow_simultaneous))

    # F: load limit, peak definition, not-simultaneous rule.
    upper = max(
        problem.base_w[w][t] + sum(p for p, _, _ in covering[(w, t)])
        for w in WEEKDAYS
        for t in range(STEPS_PER_DAY)
    )
    peak_w = model.new_int_var(0, max(upper, 0), "peak_w")
    for weekday in WEEKDAYS:
        for step in range(STEPS_PER_DAY):
            terms = covering[(weekday, step)]
            load = problem.base_w[weekday][step] + sum(p * var for p, var, _ in terms)
            model.add(peak_w >= load)
            if enforce_limit and problem.limit_w is not None:
                model.add(load <= problem.limit_w)
            exclusive = [var for _, var, allowed in terms if not allowed]
            if enforce_not_simultaneous and len(exclusive) > 1:
                model.add(sum(exclusive) <= 1)

    # G: objective terms.
    cost = cp_model.LinearExpr.sum(
        [t.cost_by_start[s] * v for t in problem.tasks for s, v in starts[t.appliance_id].items()]
    )
    misses = cp_model.LinearExpr.sum(
        [
            v
            for t in problem.tasks
            for s, v in starts[t.appliance_id].items()
            if not t.in_preferred_window(s)
        ]
    )
    movement = cp_model.LinearExpr.sum(
        [t.displacement(s) * v for t in problem.tasks for s, v in starts[t.appliance_id].items()]
    )
    return BuiltModel(model, starts, peak_w, cost, misses, movement)
