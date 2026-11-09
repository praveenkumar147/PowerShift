from __future__ import annotations

from powershift.domain.appliance import ApplianceMode, validate_appliance
from powershift.domain.time_window import TimeWindow
from tests.factories import fixed_spec, flexible_schedule, flexible_spec


def test_valid_fixed_and_flexible_appliances_pass() -> None:
    assert validate_appliance(fixed_spec()) == {}
    assert validate_appliance(flexible_spec()) == {}


def test_fixed_appliance_needs_at_least_one_block() -> None:
    errors = validate_appliance(fixed_spec(fixed_blocks=()))
    assert "fixed_blocks" in errors


def test_fixed_blocks_must_not_overlap() -> None:
    spec = fixed_spec(fixed_blocks=(TimeWindow(1080, 1380), TimeWindow(1320, 60)))
    assert "overlap" in validate_appliance(spec)["fixed_blocks"]


def test_fixed_appliance_rejects_flexible_settings() -> None:
    errors = validate_appliance(fixed_spec(flexible=flexible_schedule()))
    assert "flexible" in errors


def test_flexible_appliance_needs_schedule_and_no_fixed_blocks() -> None:
    errors = validate_appliance(flexible_spec(flexible=None, fixed_blocks=(TimeWindow(0, 60),)))
    assert set(errors) == {"flexible", "fixed_blocks"}


def test_run_longer_than_window_is_rejected() -> None:
    spec = flexible_spec(
        flexible=flexible_schedule(run_duration_minutes=180, allowed_window=TimeWindow(1320, 1440))
    )
    message = validate_appliance(spec)["flexible.run_duration_minutes"]
    assert "180-minute run cannot fit" in message
    assert "22:00-24:00" in message


def test_current_start_must_let_run_finish_inside_window() -> None:
    late_start = flexible_schedule(current_start_minute=1260)  # 21:00 + 90 min > 22:00
    errors = validate_appliance(flexible_spec(flexible=late_start))
    assert set(errors) == {"flexible.current_start_minute"}


def test_overnight_window_accepts_run_crossing_midnight() -> None:
    overnight = flexible_schedule(
        allowed_window=TimeWindow(1320, 360),  # 22:00-06:00
        current_start_minute=1380,  # 23:00 -> 00:30
    )
    assert validate_appliance(flexible_spec(flexible=overnight)) == {}


def test_preferred_window_must_be_inside_allowed_window() -> None:
    outside = flexible_schedule(preferred_window=TimeWindow(360, 600))  # starts 06:00 < 08:00
    assert (
        "inside" in validate_appliance(flexible_spec(flexible=outside))["flexible.preferred_window"]
    )


def test_preferred_window_must_fit_the_run() -> None:
    short = flexible_schedule(preferred_window=TimeWindow(600, 660))  # 60 min < 90 min run
    assert (
        "shorter" in validate_appliance(flexible_spec(flexible=short))["flexible.preferred_window"]
    )


def test_mode_enum_values_are_stable() -> None:
    # These strings are stored in the database; changing them needs a migration.
    assert [m.value for m in ApplianceMode] == ["fixed", "flexible"]
