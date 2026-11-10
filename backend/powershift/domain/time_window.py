"""Times of day and windows that may wrap past midnight.

Conventions used everywhere in PowerShift:
- A time of day is "minutes since midnight". 0 = 00:00, 1439 = 23:59.
- Every time is a multiple of TIME_STEP_MINUTES (15). Hourly scheduling uses
  multiples of 60; 15-minute steps keep the data ready for finer slots later.
- A window has a start (0-1439) and an end (1-1440). If end <= start, the window
  wraps past midnight: 22:00 -> 06:00 is start=1320, end=360 (8 hours).
  0 -> 1440 is the whole day.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

MINUTES_PER_DAY = 24 * 60
TIME_STEP_MINUTES = 15
STEPS_PER_DAY = MINUTES_PER_DAY // TIME_STEP_MINUTES


@dataclass(frozen=True, slots=True)
class TimeWindow:
    start_minute: int
    end_minute: int

    @property
    def length_minutes(self) -> int:
        if self.end_minute > self.start_minute:
            return self.end_minute - self.start_minute
        return self.end_minute + MINUTES_PER_DAY - self.start_minute

    def offset_of(self, minute: int) -> int:
        """Minutes from the window start to `minute`, going forward through midnight."""
        return (minute - self.start_minute) % MINUTES_PER_DAY

    def fits(self, start_minute: int, duration_minutes: int) -> bool:
        """True if a run of `duration_minutes` starting at `start_minute` stays inside."""
        return self.offset_of(start_minute) + duration_minutes <= self.length_minutes

    def contains_window(self, inner: TimeWindow) -> bool:
        return self.fits(inner.start_minute, inner.length_minutes)

    def steps(self) -> list[int]:
        """Indexes of the 15-minute steps of the day this window covers (0-95)."""
        first = self.start_minute // TIME_STEP_MINUTES
        count = self.length_minutes // TIME_STEP_MINUTES
        return [(first + i) % STEPS_PER_DAY for i in range(count)]


def run_window(start_minute: int, duration_minutes: int) -> TimeWindow:
    """The window occupied by a run (wrapping past midnight if needed)."""
    end = (start_minute + duration_minutes) % MINUTES_PER_DAY
    return TimeWindow(start_minute, end if end != 0 else MINUTES_PER_DAY)


def windows_overlap(windows: Iterable[TimeWindow]) -> bool:
    seen: set[int] = set()
    for window in windows:
        steps = set(window.steps())
        if seen & steps:
            return True
        seen |= steps
    return False


def format_minute(minute: int, twelve_hour: bool = False) -> str:
    """1320 -> '22:00' (or '10:00 PM'); 1440 -> '24:00' (or '12:00 AM')."""
    hours, minutes = divmod(minute, 60)
    if not twelve_hour:
        return f"{hours:02d}:{minutes:02d}"
    suffix = "AM" if hours % 24 < 12 else "PM"
    return f"{hours % 12 or 12}:{minutes:02d} {suffix}"
