"""Substeps G-H: objectives, solver execution and status handling.

The strongest check here is brute force: for small households every possible
schedule is enumerated and scored in plain Python, and the solver must return
exactly the best one for each goal.
"""

from __future__ import annotations

import itertools

import pytest

from powershift.optimization.problem import (
    Priority,
    SchedulingProblem,
    baseline_starts,
    build_problem,
    evaluate,
)
from powershift.optimization.runner import (
    WEIGHT_SCALE,
    SolverSettings,
    SolveStatus,
    overall_status,
    solve,
)
from tests.factories import flat_tariff, tou_tariff
from tests.optimization.helpers import fixed, flex, hhmm, numbered, window

SETTINGS = SolverSettings(time_limit_seconds=20)
# TOU prices: 00-06 @3, 06-18 @5, 18-22 @8 (peak), 22-24 @3.


def brute_force(problem: SchedulingProblem, priority: Priority, weight: int = 50) -> dict[int, int]:
    """The true optimum by trying every combination of start times."""
    reference = evaluate(problem, baseline_starts(problem))
    cost_ref, peak_ref = max(reference.cost, 1), max(reference.peak_w, 1)

    def key(starts: dict[int, int]) -> tuple[int, ...]:
        e = evaluate(problem, starts)
        tail = (e.preferred_misses, e.movement_minutes)
        if priority is Priority.COST:
            return (e.cost, e.peak_w, *tail)
        if priority is Priority.PEAK:
            return (e.peak_w, e.cost, *tail)
        blend = weight * peak_ref * e.cost + (WEIGHT_SCALE - weight) * cost_ref * e.peak_w
        return (blend, e.cost, e.peak_w, *tail)

    ids = [t.appliance_id for t in problem.tasks]
    options = (
        dict(zip(ids, combo, strict=True))
        for combo in itertools.product(*(t.candidates for t in problem.tasks))
    )
    feasible = [s for s in options if evaluate(problem, s).feasible]
    best = min(feasible, key=key)
    assert sum(key(s) == key(best) for s in feasible) == 1, (
        "test household must have a unique optimum"
    )
    return best


def household() -> SchedulingProblem:
    """Evening-heavy home: TV and lights fixed in the evening; three flexible appliances."""
    return build_problem(
        numbered(
            fixed("Fridge", 150, (window("00:00", "00:00"),)),
            fixed("TV and lights", 400, (window("18:00", "23:00"),)),
            flex("Washer", 2000, 90, window("06:00", "23:00"), "19:00", allow_simultaneous=False),
            flex(
                "Dishwasher", 1800, 120, window("19:00", "07:00"), "20:00", allow_simultaneous=False
            ),
            flex("Water heater", 3000, 60, window("04:00", "09:00"), "07:00"),
        ),
        tou_tariff(),
        limit_kw=5,
    )


def test_cost_goal_moves_a_run_to_the_cheapest_hours_with_least_movement() -> None:
    # 2 kW x 90 min. Cheapest in its 06:00-23:00 window is the 5.00 band (run must end by 18:00).
    # All starts 06:00..16:00 cost the same, so the closest to the usual 19:00 wins: 16:00.
    washer = flex("Washer", 2000, 90, window("06:00", "23:00"), "19:00")
    result = solve(build_problem(numbered(washer), tou_tariff(), None), Priority.COST, SETTINGS)

    assert result.status is SolveStatus.OPTIMAL
    assert result.starts == {1: hhmm("16:00")}
    assert result.cost == 105 * 10_000  # 3 kWh x 5 x 7 days (was 168 at 19:00)
    assert [s.name for s in result.stages] == ["cost", "peak", "preferred_window", "movement"]
    assert all(s.status == "OPTIMAL" for s in result.stages)


def test_cost_goal_uses_peak_as_tie_break() -> None:
    # Both can run in the cheap 5.00 band; with equal cost the solver must not stack them.
    a = flex("A", 2000, 60, window("10:00", "13:00"), "10:00")
    b = flex("B", 2000, 60, window("10:00", "13:00"), "10:00")
    result = solve(build_problem(numbered(a, b), tou_tariff(), None), Priority.COST, SETTINGS)
    assert result.peak_w == 2000
    assert len(set(result.starts.values())) == 2


def test_peak_goal_spreads_load_even_under_a_flat_tariff() -> None:
    # Flat price: cost cannot change, but the peak can. TV (1 kW) is on 19:00-21:00.
    tv = fixed("TV", 1000, (window("19:00", "21:00"),))
    a = flex("A", 2000, 60, window("18:00", "23:00"), "19:00")
    b = flex("B", 2000, 60, window("18:00", "23:00"), "19:00")
    problem = build_problem(numbered(tv, a, b), flat_tariff("6"), None)

    result = solve(problem, Priority.PEAK, SETTINGS)

    assert evaluate(problem, baseline_starts(problem)).peak_w == 5000
    assert result.peak_w == 2000  # each alone, away from the TV
    assert sorted(result.starts.values()) == [hhmm("18:00"), hhmm("21:00")]
    assert result.cost == evaluate(problem, baseline_starts(problem)).cost  # flat: same cost


def test_preferred_window_breaks_ties_but_never_costs_money() -> None:
    cheap_band = window("06:00", "18:00")
    inside = flex("A", 1000, 60, cheap_band, "06:00", preferred=window("14:00", "16:00"))
    result = solve(build_problem(numbered(inside), tou_tariff(), None), Priority.COST, SETTINGS)
    assert result.starts == {1: hhmm("14:00")} and result.preferred_misses == 0

    # Preferred window is in the expensive band: cost wins, the miss is reported.
    evening = flex(
        "B", 1000, 60, window("06:00", "22:00"), "19:00", preferred=window("19:00", "21:00")
    )
    result = solve(build_problem(numbered(evening), tou_tariff(), None), Priority.COST, SETTINGS)
    assert result.starts == {1: hhmm("17:00")} and result.preferred_misses == 1


@pytest.mark.parametrize("priority", list(Priority))
def test_solver_matches_brute_force_optimum(priority: Priority) -> None:
    problem = household()
    result = solve(problem, priority, SETTINGS)
    assert result.status is SolveStatus.OPTIMAL
    assert result.starts == brute_force(problem, priority)
    assert evaluate(problem, result.starts).feasible


@pytest.mark.parametrize("weight", [0, 25, 75, 100])
def test_balanced_weight_matches_brute_force(weight: int) -> None:
    problem = household()
    result = solve(
        problem, Priority.BALANCED, SolverSettings(time_limit_seconds=20, balance_weight=weight)
    )
    assert result.starts == brute_force(problem, Priority.BALANCED, weight)


def test_cost_and_peak_goals_trade_off() -> None:
    problem = household()
    cheapest = solve(problem, Priority.COST, SETTINGS)
    flattest = solve(problem, Priority.PEAK, SETTINGS)
    balanced = solve(problem, Priority.BALANCED, SETTINGS)

    assert cheapest.cost is not None and flattest.cost is not None and balanced.cost is not None
    assert (
        cheapest.peak_w is not None and flattest.peak_w is not None and balanced.peak_w is not None
    )
    assert cheapest.cost <= balanced.cost <= flattest.cost
    assert flattest.peak_w <= balanced.peak_w <= cheapest.peak_w


def test_never_worse_than_the_current_schedule_when_it_is_feasible() -> None:
    # The usual start is always a candidate, so a valid current schedule is a
    # fallback the solver can only match or beat.
    problem = build_problem(
        numbered(
            fixed("TV and lights", 400, (window("18:00", "23:00"),)),
            flex("Washer", 2000, 90, window("06:00", "23:00"), "19:30"),
            flex("Water heater", 3000, 60, window("04:00", "09:00"), "07:15"),
        ),
        tou_tariff(),
        limit_kw=5,
    )
    today = evaluate(problem, baseline_starts(problem))
    assert today.feasible

    cheapest = solve(problem, Priority.COST, SETTINGS)
    flattest = solve(problem, Priority.PEAK, SETTINGS)

    assert cheapest.cost is not None and cheapest.cost <= today.cost
    assert flattest.peak_w is not None and flattest.peak_w <= today.peak_w


def test_infeasible_current_schedule_is_repaired() -> None:
    # Today the washer and dishwasher overlap at 20:00 although marked "not together".
    problem = household()
    assert not evaluate(problem, baseline_starts(problem)).no_conflicts
    result = solve(problem, Priority.COST, SETTINGS)
    assert evaluate(problem, result.starts).feasible


def test_infeasible_problem_returns_no_schedule() -> None:
    a = flex("A", 2000, 120, window("18:00", "20:00"), "18:00")
    b = flex("B", 2000, 120, window("18:00", "20:00"), "18:00")
    result = solve(build_problem(numbered(a, b), None, limit_kw=3), Priority.PEAK, SETTINGS)

    assert result.status is SolveStatus.INFEASIBLE
    assert result.starts == {} and result.cost is None
    assert [s.status for s in result.stages] == ["INFEASIBLE"]


def test_results_are_reproducible() -> None:
    first = solve(household(), Priority.BALANCED, SETTINGS)
    second = solve(household(), Priority.BALANCED, SETTINGS)
    assert first.starts == second.starts
    assert [s.value for s in first.stages] == [s.value for s in second.stages]


def test_invalid_weight_is_rejected() -> None:
    with pytest.raises(ValueError, match="balance_weight"):
        solve(household(), Priority.BALANCED, SolverSettings(balance_weight=101))


@pytest.mark.parametrize(
    ("stages", "expected"),
    [
        (["OPTIMAL", "OPTIMAL", "OPTIMAL"], SolveStatus.OPTIMAL),
        (["OPTIMAL", "FEASIBLE", "OPTIMAL"], SolveStatus.FEASIBLE),  # never claim optimal
        (["FEASIBLE"], SolveStatus.FEASIBLE),
        (
            ["OPTIMAL", "UNKNOWN"],
            SolveStatus.FEASIBLE,
        ),  # later stage timed out; schedule still valid
        (["INFEASIBLE"], SolveStatus.INFEASIBLE),
        (["UNKNOWN"], SolveStatus.UNKNOWN),
        (["MODEL_INVALID"], SolveStatus.MODEL_INVALID),
        ([], SolveStatus.UNKNOWN),
    ],
)
def test_status_interpretation(stages: list[str], expected: SolveStatus) -> None:
    assert overall_status(stages) is expected
