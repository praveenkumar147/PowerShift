"""Substep I: the independent validator must accept correct schedules and catch
every kind of broken one, without help from the solver."""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import powershift.optimization.validation as validation_module
from powershift.optimization.problem import COST_SCALE, Priority, build_problem
from powershift.optimization.runner import SolverSettings, solve
from powershift.optimization.validation import ScheduledRun, ValidationReport, validate_schedule
from tests.factories import tou_tariff
from tests.optimization.helpers import fixed, flex, hhmm, numbered, window

TV = fixed("TV", 1000, (window("19:00", "21:00"),))
WASHER = flex("Washer", 2000, 90, window("06:00", "23:00"), "19:00", allow_simultaneous=False)
DRYER = flex("Dryer", 2000, 60, window("06:00", "23:00"), "20:00", allow_simultaneous=False)
HOME = numbered(TV, WASHER, DRYER)  # ids: TV 1, Washer 2, Dryer 3
LIMIT = 3.5


def run(start: str, end: str) -> ScheduledRun:
    return ScheduledRun(hhmm(start), hhmm(end) or 1440)


GOOD = {2: run("10:00", "11:30"), 3: run("12:00", "13:00")}


def check(schedule: dict[int, ScheduledRun], **reported: object) -> ValidationReport:
    return validate_schedule(
        HOME,
        schedule,
        tou_tariff(),
        LIMIT,
        reported.get("cost"),
        reported.get("peak"),  # type: ignore[arg-type]
        2026,
        11,
    )


def failed(report: ValidationReport) -> set[str]:
    return {c.code for c in report.checks if not c.passed}


def test_valid_schedule_passes_every_check() -> None:
    report = check(GOOD)
    assert report.passed
    assert [c.code for c in report.checks] == [
        "assignment",
        "time_grid",
        "duration",
        "window",
        "load_limit",
        "not_simultaneous",
        "objective",
    ]


def test_missing_and_non_flexible_appliances_are_caught() -> None:
    assert failed(check({2: GOOD[2]})) == {"assignment"}  # dryer missing
    report = check({**GOOD, 1: run("10:00", "11:00")})  # TV is fixed
    assert failed(report) == {"assignment"}
    assert "TV is not a flexible appliance" in report.checks[0].detail


def test_off_grid_or_impossible_times_are_caught() -> None:
    report = check({2: ScheduledRun(605, 695), 3: GOOD[3]})
    assert failed(report) == {"time_grid"}
    assert len(report.checks) == 2  # stops: later checks need valid times


def test_wrong_duration_is_caught() -> None:
    report = check({2: run("10:00", "11:00"), 3: GOOD[3]})  # washer needs 90 min
    assert "duration" in failed(report)
    assert "Washer runs 60 min instead of 90 min" in report.checks[2].detail


def test_run_outside_its_window_is_caught() -> None:
    report = check({2: run("05:00", "06:30"), 3: GOOD[3]})  # window starts 06:00
    assert failed(report) == {"window"}


def test_load_limit_violation_is_caught() -> None:
    # Washer (2 kW) and dryer (2 kW) both during the TV's 1 kW: 5 kW against a 3.5 kW limit.
    report = check({2: run("19:00", "20:30"), 3: run("19:00", "20:00")})
    assert {"load_limit", "not_simultaneous"} <= failed(report)


def test_not_simultaneous_overlap_is_caught_even_within_the_limit() -> None:
    report = validate_schedule(
        HOME,
        {2: run("10:00", "11:30"), 3: run("11:00", "12:00")},
        tou_tariff(),
        None,
        None,
        None,
        2026,
        11,
    )
    assert failed(report) == {"not_simultaneous"}
    assert "210 min per week" in report.checks[5].detail  # 30 min overlap x 7 days


def test_wrong_reported_numbers_are_caught() -> None:
    assert failed(check(GOOD, peak=9.9)) == {"objective"}
    assert failed(check(GOOD, cost=Decimal("1.00"))) == {"objective"}


def test_solver_output_passes_validation_with_its_own_reported_numbers() -> None:
    problem = build_problem(HOME, tou_tariff(), LIMIT)
    result = solve(problem, Priority.COST, SolverSettings())
    durations = {t.appliance_id: t.duration_minutes for t in problem.tasks}
    schedule = {
        i: ScheduledRun(s, (s + durations[i]) % 1440 or 1440) for i, s in result.starts.items()
    }
    assert result.cost is not None and result.peak_w is not None

    report = check(schedule, cost=Decimal(result.cost) / COST_SCALE, peak=result.peak_w / 1000)

    assert report.passed, [c for c in report.checks if not c.passed]


def test_validator_is_independent_of_the_solver() -> None:
    """The validator must not import OR-Tools, the model builder or the runner."""
    tree = ast.parse(Path(validation_module.__file__).read_text(encoding="utf-8"))
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert not any(
        name and (name.startswith("ortools") or name.endswith((".builder", ".runner", ".problem")))
        for name in imported
    )
