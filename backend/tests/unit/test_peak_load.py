"""Peak load analysis: worked examples and edge cases.

Household used by most tests (all on every day unless stated):
- Fridge   150 W, duty 0.4, all day        -> 0.15 kW worst / 0.06 kW expected
- Heater   3 kW, duty 1, 07:00-08:00        (fixed, heavy)
- Washer   2 kW, duty 0.5, 19:00-20:30      (flexible, heavy, not simultaneous)
- Kettle   2 kW, duty 1, 19:30-19:45        (fixed, heavy)
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from powershift.calculation.peak_load import (
    HIGH_DEMAND_FRACTION,
    analyse_day,
    build_demands,
    find_windows,
    summarise_week,
    worst_weekday,
)
from powershift.domain.appliance import ApplianceCategory
from powershift.domain.time_window import TimeWindow
from tests.factories import fixed_spec, flexible_schedule, flexible_spec

FRIDGE = fixed_spec(name="Fridge")
HEATER = fixed_spec(
    name="Heater",
    rated_power_w=3000,
    duty_cycle=1.0,
    fixed_blocks=(TimeWindow(420, 480),),
    category=ApplianceCategory.WATER_HEATING,
)
WASHER = flexible_spec(name="Washer", flexible=flexible_schedule(current_start_minute=1140))
KETTLE = fixed_spec(
    name="Kettle", rated_power_w=2000, duty_cycle=1.0, fixed_blocks=(TimeWindow(1170, 1185),)
)


def demands(*specs):  # type: ignore[no-untyped-def]
    return build_demands([(i + 1, spec) for i, spec in enumerate(specs)])


def step(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return (int(hours) * 60 + int(minutes)) // 15


def test_worst_case_and_expected_demand_differ_by_duty_cycle() -> None:
    day = analyse_day(demands(FRIDGE, WASHER), weekday=0, load_limit_kw=None)

    s = day.steps[step("19:00")]
    assert s.worst_kw == pytest.approx(2.15)  # 0.15 + 2.0
    assert s.expected_kw == pytest.approx(1.06)  # 0.06 + 1.0
    assert s.fixed_kw == pytest.approx(0.15) and s.flexible_kw == pytest.approx(2.0)
    assert day.steps[step("03:00")].worst_kw == pytest.approx(0.15)


def test_peak_is_found_at_15_minute_resolution() -> None:
    # 19:30-19:45: fridge 0.15 + washer 2 + kettle 2 = 4.15 kW, for 15 minutes only.
    day = analyse_day(demands(FRIDGE, WASHER, KETTLE), 0, None)

    assert day.peak_kw == pytest.approx(4.15)
    assert [(w.start_minute, w.end_minute) for w in day.peak_windows] == [(1170, 1185)]
    assert [d.name for d in day.peak_step.running] == ["Kettle", "Washer", "Fridge"]


def test_several_separate_peak_windows() -> None:
    heater_evening = replace(HEATER, fixed_blocks=(TimeWindow(420, 480), TimeWindow(1260, 1320)))
    day = analyse_day(demands(heater_evening), 0, None)
    assert [(w.start_minute, w.end_minute) for w in day.peak_windows] == [(420, 480), (1260, 1320)]


def test_load_limit_violation_window_and_culprits() -> None:
    day = analyse_day(demands(FRIDGE, WASHER, KETTLE), 0, load_limit_kw=4.0)

    (violation,) = day.violations
    assert (violation.window.start_minute, violation.window.end_minute) == (1170, 1185)
    assert violation.max_kw == pytest.approx(4.15)
    assert [d.name for d in violation.appliances] == ["Kettle", "Washer", "Fridge"]
    assert day.minutes_over_limit == 15


def test_demand_exactly_at_the_limit_is_not_a_violation() -> None:
    day = analyse_day(demands(FRIDGE, WASHER, KETTLE), 0, load_limit_kw=4.15)
    assert day.violations == ()


def test_no_limit_means_no_violations_and_high_demand_relative_to_peak() -> None:
    day = analyse_day(demands(FRIDGE, WASHER, KETTLE), 0, load_limit_kw=None)
    assert day.violations == ()
    # 80% of 4.15 = 3.32 kW: only the 15 minutes at 4.15 qualify (19:00-19:30 is 2.15).
    assert [(e.window.start_minute, e.window.end_minute) for e in day.high_demand] == [(1170, 1185)]


def test_high_demand_threshold_uses_the_load_limit() -> None:
    # Limit 2.5 kW -> threshold 2.0 kW. High demand: 19:00-20:30 (2.15 kW)
    # and the heater's 07:00-08:00 (3.15 kW).
    day = analyse_day(demands(FRIDGE, HEATER, WASHER), 0, load_limit_kw=2.5)
    assert HIGH_DEMAND_FRACTION == 0.8
    assert [(e.window.start_minute, e.window.end_minute) for e in day.high_demand] == [
        (420, 480),
        (1140, 1230),
    ]


def test_overlap_of_heavy_appliances() -> None:
    day = analyse_day(demands(FRIDGE, WASHER, KETTLE), 0, None)

    (overlap,) = day.overlaps
    assert [d.name for d in overlap.appliances] == ["Kettle", "Washer"]  # fridge is not heavy
    assert overlap.max_kw == pytest.approx(4.0)


def test_conflict_between_appliances_not_allowed_together() -> None:
    dishwasher = flexible_spec(
        name="Dishwasher",
        rated_power_w=1800,
        flexible=flexible_schedule(current_start_minute=1200, run_duration_minutes=60),
    )
    day = analyse_day(demands(WASHER, dishwasher), 0, None)

    (conflict,) = day.conflicts
    assert (conflict.window.start_minute, conflict.window.end_minute) == (1200, 1230)  # 20:00-20:30
    assert {d.name for d in conflict.appliances} == {"Washer", "Dishwasher"}


def test_windows_merge_across_midnight() -> None:
    ac = fixed_spec(
        name="AC", rated_power_w=1500, duty_cycle=0.6, fixed_blocks=(TimeWindow(1350, 120),)
    )
    day = analyse_day(demands(ac), 0, load_limit_kw=1.0)

    (violation,) = day.violations
    assert (violation.window.start_minute, violation.window.end_minute) == (
        1350,
        120,
    )  # 22:30-02:00
    assert violation.window.minutes == 210


def test_find_windows_edge_cases() -> None:
    assert find_windows([False] * 4) == []
    (whole,) = find_windows([True] * 96)
    assert (whole.start_minute, whole.end_minute, whole.minutes) == (0, 1440, 1440)
    flags = [True, False, False, True]
    assert [(w.first_step, w.step_count) for w in find_windows(flags)] == [(3, 2)]


def test_operating_days_change_the_daily_peak() -> None:
    week = summarise_week(demands(FRIDGE, WASHER), load_limit_kw=2.0)  # washer Mon, Thu, Sat

    assert [round(d.peak_kw, 2) for d in week] == [2.15, 0.15, 0.15, 2.15, 0.15, 2.15, 0.15]
    assert [d.minutes_over_limit for d in week] == [90, 0, 0, 90, 0, 90, 0]
    assert worst_weekday(week) == 0  # tie -> earliest day


def test_empty_household() -> None:
    day = analyse_day([], 0, load_limit_kw=5.0)
    assert day.peak_kw == 0 and day.peak_windows == ()
    assert day.violations == day.high_demand == day.overlaps == day.conflicts == ()
    assert len(day.steps) == 96
