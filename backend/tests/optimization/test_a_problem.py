"""Substep A: building and validating the scheduling problem."""

from __future__ import annotations

from powershift.optimization.problem import (
    Priority,
    build_problem,
    candidate_starts,
    validate_problem,
)
from tests.factories import tou_tariff
from tests.optimization.helpers import fixed, flex, hhmm, numbered, window

WASHER = flex("Washer", 2000, 90, window("06:00", "23:00"), "19:00")


def test_candidates_are_grid_points_whose_run_fits_plus_the_current_start() -> None:
    # Window 20:30-23:00, 90-minute run: on the hour only 21:00 fits (21:30 would end at 23:00 too).
    starts = candidate_starts(window("20:30", "23:00"), 90, current=hhmm("20:30"), step_minutes=60)
    assert starts == (hhmm("20:30"), hhmm("21:00"))
    assert candidate_starts(window("20:30", "23:00"), 90, hhmm("20:30"), 30) == (1230, 1260, 1290)


def test_overnight_windows_yield_candidates_on_both_sides_of_midnight() -> None:
    starts = candidate_starts(window("22:00", "06:00"), 120, current=hhmm("22:00"), step_minutes=60)
    assert starts == (0, 60, 120, 180, 240, 1320, 1380)


def test_fixed_appliances_become_base_load_and_flexible_ones_become_tasks() -> None:
    fridge = fixed("Fridge", 150, (window("00:00", "00:00"),))
    problem = build_problem(
        numbered(fridge, WASHER), tou_tariff(), limit_kw=5, start_step_minutes=60
    )

    assert [t.name for t in problem.tasks] == ["Washer"]
    assert problem.base_w[0][0] == 150 and problem.base_w[6][95] == 150
    assert problem.limit_w == 5000


def test_power_rounds_up_and_limit_rounds_down() -> None:
    lamp = flex("Lamp", 9.5, 60, window("00:00", "00:00"), "18:00")
    problem = build_problem(numbered(lamp), None, limit_kw=2.9999, start_step_minutes=60)
    assert problem.tasks[0].power_w == 10
    assert problem.limit_w == 2999


def test_weekly_cost_of_each_start_uses_time_of_use_prices() -> None:
    # 2 kW for 90 min = 3 kWh per run, 7 days a week.
    # 19:00 start: peak price 8 -> 3 x 8 x 7 = 168.00 ; 13:00 start: 5 -> 105.00 ; 22:00: 3 -> 63.00
    problem = build_problem(numbered(WASHER), tou_tariff(), None)
    costs = problem.tasks[0].cost_by_start
    assert costs[hhmm("19:00")] == 168 * 10_000
    assert costs[hhmm("13:00")] == 105 * 10_000
    # 21:00-22:30 straddles two prices: 1 h at 8 and 0.5 h at 3 -> (2x8 + 1x3) x 7 = 133
    assert costs[hhmm("21:00")] == 133 * 10_000


def test_operating_days_limit_cost_and_base_load() -> None:
    weekday_washer = flex(
        "Washer", 2000, 60, window("00:00", "00:00"), "19:00", operating_days=(0, 2)
    )
    problem = build_problem(numbered(weekday_washer), tou_tariff(), None)
    assert problem.tasks[0].cost_by_start[hhmm("19:00")] == 2 * 8 * 2 * 10_000  # 2 kWh x 8 x 2 days
    assert problem.tasks[0].days == (0, 2)


def test_input_validation_explains_unsolvable_setups() -> None:
    tight = flex("Dishwasher", 1800, 90, window("20:30", "22:00"), "20:30")
    problem = build_problem(numbered(tight), None, None, start_step_minutes=60)

    issues = {i.code: i for i in validate_problem(problem, Priority.COST)}
    assert "no_tariff" in issues  # cost goal without a tariff
    assert "no_start_fits" not in issues  # the current 20:30 start is always a candidate

    empty = build_problem(numbered(fixed("Fridge", 150, (window("00:00", "00:00"),))), None, None)
    assert [i.code for i in validate_problem(empty, Priority.PEAK)] == ["no_flexible_appliances"]


def test_peak_goal_needs_no_tariff() -> None:
    problem = build_problem(numbered(WASHER), None, None)
    assert validate_problem(problem, Priority.PEAK) == []
    assert problem.tasks[0].cost_by_start[hhmm("19:00")] == 0


def test_only_time_of_use_makes_cost_depend_on_time() -> None:
    assert build_problem(numbered(WASHER), tou_tariff(), None).cost_is_time_dependent
    assert not build_problem(numbered(WASHER), None, None).cost_is_time_dependent
