"""Substeps B-F: variables and constraints, tested by asking CP-SAT for ANY feasible
schedule (no objective) and checking the constraints decide the outcome."""

from __future__ import annotations

from ortools.sat.python import cp_model

from powershift.optimization.builder import build_model
from powershift.optimization.problem import SchedulingProblem, build_problem
from tests.optimization.helpers import fixed, flex, hhmm, numbered, window


def solve(problem: SchedulingProblem, **switches: bool) -> tuple[str, dict[int, int]]:
    built = build_model(problem, **switches)
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    status = solver.solve(built.model)
    chosen = (
        {
            appliance: next(s for s, v in vars_.items() if solver.value(v))
            for appliance, vars_ in built.starts.items()
        }
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        else {}
    )
    return solver.status_name(status), chosen


def test_b_one_boolean_per_candidate_start() -> None:
    washer = flex("Washer", 2000, 90, window("20:30", "23:00"), "20:30")
    built = build_model(build_problem(numbered(washer), None, None))
    assert sorted(built.starts[1]) == [hhmm("20:30"), hhmm("21:00")]


def test_c_exactly_one_start_per_appliance() -> None:
    a = flex("A", 1000, 60, window("00:00", "00:00"), "10:00")
    b = flex("B", 1000, 60, window("00:00", "00:00"), "11:00")
    status, chosen = solve(build_problem(numbered(a, b), None, None))
    assert status == "OPTIMAL"
    assert set(chosen) == {1, 2}  # one start each, so each gets its full duration


def test_d_starts_outside_the_window_do_not_exist() -> None:
    heater = flex("Heater", 3000, 60, window("04:00", "09:00"), "07:00")
    built = build_model(build_problem(numbered(heater), None, None))
    assert all(window("04:00", "09:00").fits(s, 60) for s in built.starts[1])
    assert hhmm("08:00") in built.starts[1] and hhmm("09:00") not in built.starts[1]


def test_e_runs_are_contiguous_and_wrap_midnight() -> None:
    dishwasher = flex("Dishwasher", 1800, 120, window("22:00", "06:00"), "23:00")
    problem = build_problem(numbered(dishwasher), None, None)
    task = problem.tasks[0]
    steps = task.steps_for(hhmm("23:00"))
    assert steps == [92, 93, 94, 95, 0, 1, 2, 3]  # 23:00-01:00, unbroken across midnight


def test_f_load_limit_forces_appliances_apart() -> None:
    # Two 2 kW appliances, both allowed 18:00-20:00, 1 h each, limit 3 kW:
    # they cannot overlap, so one must run 18:00-19:00 and the other 19:00-20:00.
    a = flex("A", 2000, 60, window("18:00", "20:00"), "18:00")
    b = flex("B", 2000, 60, window("18:00", "20:00"), "18:00")
    status, chosen = solve(build_problem(numbered(a, b), None, limit_kw=3))
    assert status == "OPTIMAL"
    assert sorted(chosen.values()) == [hhmm("18:00"), hhmm("19:00")]


def test_f_load_limit_includes_fixed_base_load() -> None:
    # 2.5 kW heater must avoid 19:00-21:00, where a 1 kW fixed load would push it over 3 kW.
    tv = fixed("TV", 1000, (window("19:00", "21:00"),))
    heater = flex("Heater", 2500, 60, window("18:00", "22:00"), "19:00")
    status, chosen = solve(build_problem(numbered(tv, heater), None, limit_kw=3))
    assert status == "OPTIMAL"
    assert chosen[2] in (hhmm("18:00"), hhmm("21:00"))


def test_f_load_limit_can_make_the_model_infeasible() -> None:
    a = flex("A", 2000, 120, window("18:00", "20:00"), "18:00")
    b = flex("B", 2000, 120, window("18:00", "20:00"), "18:00")
    status, _ = solve(build_problem(numbered(a, b), None, limit_kw=3))
    assert status == "INFEASIBLE"
    status, _ = solve(build_problem(numbered(a, b), None, limit_kw=3), enforce_limit=False)
    assert status == "OPTIMAL"  # the limit was the only obstacle


def test_f_not_simultaneous_appliances_never_overlap() -> None:
    a = flex("Washer", 500, 60, window("10:00", "12:00"), "10:00", allow_simultaneous=False)
    b = flex("Dryer", 500, 60, window("10:00", "12:00"), "10:00", allow_simultaneous=False)
    status, chosen = solve(build_problem(numbered(a, b), None, None))
    assert status == "OPTIMAL"
    assert sorted(chosen.values()) == [hhmm("10:00"), hhmm("11:00")]


def test_f_not_simultaneous_only_counts_on_shared_days() -> None:
    # Same slot is fine when they never run on the same weekday.
    a = flex(
        "A",
        500,
        120,
        window("10:00", "12:00"),
        "10:00",
        allow_simultaneous=False,
        operating_days=(0,),
    )
    b = flex(
        "B",
        500,
        120,
        window("10:00", "12:00"),
        "10:00",
        allow_simultaneous=False,
        operating_days=(1,),
    )
    status, chosen = solve(build_problem(numbered(a, b), None, None))
    assert status == "OPTIMAL" and chosen == {1: hhmm("10:00"), 2: hhmm("10:00")}


def test_fixed_load_above_the_limit_is_infeasible_whatever_the_schedule() -> None:
    oven = fixed("Oven", 3500, (window("19:00", "20:00"),))
    lamp = flex("Lamp", 10, 60, window("00:00", "00:00"), "10:00")
    status, _ = solve(build_problem(numbered(oven, lamp), None, limit_kw=3))
    assert status == "INFEASIBLE"
