from __future__ import annotations

import pytest

from powershift.domain.time_window import TimeWindow, run_window, windows_overlap


@pytest.mark.parametrize(
    ("start", "end", "expected_minutes"),
    [
        (360, 720, 360),  # 06:00-12:00
        (1320, 360, 480),  # 22:00-06:00 wraps midnight
        (0, 1440, 1440),  # whole day
        (600, 600, 1440),  # 10:00-10:00 = a full 24 h starting at 10:00
        (1380, 1440, 60),  # 23:00-24:00
    ],
)
def test_window_length(start: int, end: int, expected_minutes: int) -> None:
    assert TimeWindow(start, end).length_minutes == expected_minutes


def test_run_fits_in_overnight_window() -> None:
    night = TimeWindow(1320, 360)  # 22:00-06:00

    assert night.fits(1320, 480)  # 22:00 for 8 h ends exactly at 06:00
    assert night.fits(60, 120)  # 01:00-03:00
    assert not night.fits(300, 120)  # 05:00-07:00 runs past 06:00
    assert not night.fits(720, 60)  # noon is outside the window


def test_contains_window() -> None:
    allowed = TimeWindow(1200, 480)  # 20:00-08:00
    assert allowed.contains_window(TimeWindow(1380, 120))  # 23:00-02:00
    assert not allowed.contains_window(TimeWindow(420, 600))  # 07:00-10:00


def test_steps_wrap_midnight() -> None:
    assert TimeWindow(1410, 30).steps() == [94, 95, 0, 1]


def test_run_window_wraps_and_handles_midnight_end() -> None:
    assert run_window(1380, 120) == TimeWindow(1380, 60)
    assert run_window(1380, 60) == TimeWindow(1380, 1440)


def test_overlap_detection_including_wrap() -> None:
    assert not windows_overlap([TimeWindow(0, 360), TimeWindow(360, 720)])  # touching is fine
    assert windows_overlap([TimeWindow(1320, 120), TimeWindow(60, 180)])  # 01:00 in both
