# Optimization Model

*Describes the implemented Smart Scheduler (Stage 5). Code: `backend/powershift/optimization/`.*

## In plain language

> For every flexible appliance, pick **one start time** (used on every day it runs) so
> that the whole run fits its allowed window, the household never exceeds its load
> limit, appliances marked "not simultaneous" never overlap, and the chosen goal
> (lowest cost, lowest peak, or a balance) is as good as possible.

Fixed appliances are not decisions. They form the **baseline load**.

## Why CP-SAT?

CP-SAT (Google OR-Tools) solves problems made of integer and yes/no variables with
constraints, and it can **prove** that no better answer exists. That proof is what lets the
app say "optimal" honestly. A random or rule-based scheduler could never prove it.

## Inputs (`problem.py`)

| Symbol | Meaning |
|---|---|
| A | flexible appliances |
| S_a | allowed start times of appliance a: grid points (60, 30 or 15 min) whose **whole run fits the allowed window**, plus the appliance's current start |
| P_a | full power of a in W (rated × quantity, rounded **up** to whole watts) |
| D_a | days a operates |
| T | the 96 fifteen-minute steps of a day; W = Monday…Sunday |
| B[w,t] | fixed-appliance worst-case load in W (baseline) |
| L | load limit in W, rounded **down** (so an accepted schedule is truly within the limit); none if unset |
| c[a,s] | weekly energy charge of a if it starts at s (integer, units of 1/10 000 of the currency) |

CP-SAT only handles integers, hence watts and scaled money. Rounding goes in the safe
direction for the limit.

## Decision variables (`builder.py`, substep B)

- `x[a,s] ∈ {0,1}` for every a and s ∈ S_a: appliance a starts at s.
- `peak ∈ [0, max possible load]` (integer, W): the household's highest demand.

Example: a washer with window 06:00–23:00, 90-minute run, hourly grid has 16 variables
(06:00, 07:00, … 21:00) plus its current start if that is off the grid.

## Constraints

| # | Constraint | Meaning |
|---|---|---|
| C | Σₛ x[a,s] = 1 for every a | each appliance runs exactly once per operating day, so it gets its **full required duration** |
| D | variables exist only for starts that fit the window | **operating windows** are respected by construction; an out-of-window run cannot be expressed |
| E | a start s covers steps s, s+15, …, s+D−15 (wrapping past midnight) | **contiguity**: every run is one uninterrupted block |
| F1 | for every w, t: B[w,t] + Σ P_a·x[a,s] ≤ L (over runs covering t on days w ∈ D_a) | **household load limit**, worst case, every 15 minutes, every weekday |
| F2 | for every w, t: peak ≥ B[w,t] + Σ P_a·x[a,s] | defines the peak |
| F3 | for every w, t: Σ x[a,s] ≤ 1 over covering runs of "not simultaneous" appliances | **appliance-specific restriction** |

Preferred windows are **soft**: they do not forbid a start, they are a tie-break (below).

## Objective (`runner.py`, substep G)

The three goals are **multi-stage (lexicographic)**: minimise one quantity, **lock** its best
value with a constraint, then minimise the next. A later stage can never make an earlier one
worse.

| Goal | Stages in order |
|---|---|
| Lowest cost | cost → peak → preferred-window misses → movement |
| Lowest peak | peak → cost → preferred-window misses → movement |
| Balanced | blend → cost → peak → preferred-window misses → movement |

- **cost** = Σ c[a,s]·x[a,s]. Under a flat or slab tariff every c[a,s] is equal, so cost cannot
  change and the stage simply passes; only a time-of-use tariff makes timing matter.
- **preferred-window misses** = number of runs outside their preferred window.
- **movement** = total minutes the runs move from their usual start. It comes last so that,
  among equally good schedules, the one changing habits least wins. It also makes the answer
  unique, which keeps runs reproducible.

### The balanced blend (normalised, so units are never mixed)

Cost (money) and peak (watts) cannot be added directly. Each is divided by its value in the
**current** schedule, giving unit-free ratios where 1.0 means "same as today":

```
blend = w · cost / cost_ref  +  (1 − w) · peak / peak_ref          w = weight / 100
```

CP-SAT needs integers, so both sides are multiplied by 100 · cost_ref · peak_ref:

```
blend_int = weight · peak_ref · cost  +  (100 − weight) · cost_ref · peak
```

Minimising `blend_int` gives exactly the same schedule as minimising `blend`.

### The trade-off

The cheapest hours are the same for every appliance, so pure cost minimisation tends to stack
appliances there and raise the peak. Pure peak minimisation spreads them out, possibly into
expensive hours. The stage order (or the balance slider) is how the user chooses. Tests show
the ordering `cost(lowest cost) ≤ cost(balanced) ≤ cost(lowest peak)` and the reverse for peak.

## Solver statuses (never overstated)

| Status | Meaning | Shown as |
|---|---|---|
| OPTIMAL | every stage solved to proven optimality | "Optimal schedule found and verified" |
| FEASIBLE | a valid schedule exists but at least one stage hit the time limit before proving it best | "Valid schedule found, **not proven optimal**" |
| INFEASIBLE | no schedule satisfies all constraints | "No valid schedule exists" + diagnostics |
| UNKNOWN | time limit ran out before any schedule was found | "No schedule found within the time limit" |
| MODEL_INVALID | the model was rejected (a bug) | "Internal model error" |

`overall_status()` combines per-stage statuses: OPTIMAL only if **all** stages are OPTIMAL.

## Independent validation (`validation.py`, substep I)

The solver's answer is re-checked from the original appliance settings using the Stage 3–4
calculation engines (float kW and Decimal money), **not** the solver's integer model. The module
does not import OR-Tools, the builder or the runner (a test enforces this).

1. Every flexible appliance scheduled once; fixed appliances untouched.
2. Times lie on the 15-minute grid.
3. Each run has the required duration as one block.
4. Each run is inside its allowed window.
5. Household load limit respected (every step, every weekday).
6. "Not simultaneous" appliances never overlap.
7. The solver's reported cost and peak match an independent recalculation (within rounding
   tolerances derived from the integer scaling).

A schedule is shown as a recommendation **only if all checks pass**. A schedule that fails is
reported as invalid and not displayed as a result.

## Savings

`Savings = baseline monthly bill − optimized monthly bill`, both computed by the same
`measure()` function (Stage 3 energy model) for the current month. Negative savings are shown
as negative. Under a flat or slab tariff savings are 0 and the app says why.

## Infeasibility diagnostics (`diagnose.py`)

For an INFEASIBLE problem the app looks for the cause:

1. Fixed appliances alone above the limit (with the times and the peak).
2. An appliance that cannot fit under the limit anywhere in its window.
3. **Relaxation**: re-solve with one constraint group switched off. If it becomes solvable,
   that group is the blocker. For the load limit, it reports the **smallest limit that would work**.
4. "Not simultaneous" rule blocking a schedule.

## Explanations (`explain.py`)

Every sentence is generated from a measured difference between the current and the optimised
schedule (average price while running, appliances no longer overlapped, household demand while
running, limit violations fixed, preferred window). If a difference does not exist, its sentence
is not produced. Costlier or higher-demand moves are disclosed, not hidden.

## Reproducibility

Each run stores its inputs snapshot (appliances, tariff, limit), settings (goal, weight, start
step, time limit), random seed, number of workers (1), app version and OR-Tools version, plus the
full result. Single-worker search with a fixed seed and a unique final tie-break makes identical
inputs give identical schedules. Tested.

## Verification of optimality

Tests enumerate **every** possible schedule for small households in plain Python, score each
with `evaluate()`, and require the solver to return exactly the brute-force optimum for each
goal and several balance weights.

## Limits and extensions

- One start time per appliance for all its operating days (not per-day schedules).
- Start-time grid of 60, 30 or 15 minutes; the 15-minute data model is already in place.
- Hourly slots are the default; finer grids give equal or better results but take longer.
- The scheduler recommends; it does **not** change your appliance settings. Applying a
  schedule is not part of the agreed scope.
- All figures are estimates from user-entered settings, not measurements.

## Shared pipeline

Steps 1-9 live in `optimization/pipeline.py` (`run_pipeline`), which takes plain objects and touches no
database. The Smart Scheduler uses it on the real household; the Simulation Lab uses it on modified
copies. Both therefore get the same solver, the same independent validation and the same explanations.
