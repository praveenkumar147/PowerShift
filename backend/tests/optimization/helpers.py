"""Shared builders for optimization tests. Rates are invented round numbers."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from powershift.domain.appliance import ApplianceSpec
from powershift.domain.time_window import TimeWindow
from tests.factories import fixed_spec, flexible_schedule, flexible_spec

EVERY_DAY = (0, 1, 2, 3, 4, 5, 6)


def hhmm(text: str) -> int:
    hours, minutes = text.split(":")
    return int(hours) * 60 + int(minutes)


def window(start: str, end: str) -> TimeWindow:
    return TimeWindow(hhmm(start), hhmm(end) or 1440)


def flex(
    name: str, watts: float, minutes: int, allowed: TimeWindow, usual: str, **extra: Any
) -> ApplianceSpec:
    """A flexible appliance at duty cycle 1 running every day unless overridden."""
    schedule = flexible_schedule(
        run_duration_minutes=minutes,
        allowed_window=allowed,
        current_start_minute=hhmm(usual),
        preferred_window=extra.pop("preferred", None),
    )
    defaults: dict[str, Any] = {
        "name": name,
        "rated_power_w": watts,
        "duty_cycle": 1.0,
        "operating_days": EVERY_DAY,
        "allow_simultaneous": True,
        "flexible": schedule,
    }
    defaults.update(extra)
    return flexible_spec(**defaults)


def fixed(name: str, watts: float, blocks: tuple[TimeWindow, ...], **extra: Any) -> ApplianceSpec:
    return replace(
        fixed_spec(name=name, rated_power_w=watts, duty_cycle=1.0, fixed_blocks=blocks), **extra
    )


def numbered(*specs: ApplianceSpec) -> list[tuple[int, ApplianceSpec]]:
    return [(i + 1, spec) for i, spec in enumerate(specs)]
