"""Plain-language descriptions of scenario changes, generated from the actual data
(so a replaced appliance lists exactly which of its settings differ)."""

from __future__ import annotations

from collections.abc import Mapping

from powershift.calculation.appliance_energy import max_power_kw, on_minutes_per_day
from powershift.domain.appliance import ApplianceMode, ApplianceSpec
from powershift.domain.time_window import format_minute
from powershift.simulation.scenario import (
    AddAppliance,
    Change,
    ChangeTariff,
    RemoveAppliance,
    ReplaceAppliance,
    SetLoadLimit,
)

MINUTES_PER_HOUR = 60


def _hours(minutes: int) -> str:
    return f"{minutes / MINUTES_PER_HOUR:g} h"


def _days(spec: ApplianceSpec) -> str:
    count = len(spec.operating_days)
    return f"{count} day{'s' if count != 1 else ''} a week"


def appliance_summary(spec: ApplianceSpec) -> str:
    kind = "flexible" if spec.mode is ApplianceMode.FLEXIBLE else "fixed"
    kw = max_power_kw(spec)
    on = _hours(on_minutes_per_day(spec))
    return f"{kw:g} kW, {kind}, {on} on, {_days(spec)}"


def appliance_differences(old: ApplianceSpec, new: ApplianceSpec) -> list[str]:
    diffs: list[str] = []
    if old.name != new.name:
        diffs.append(f'renamed to "{new.name}"')
    if old.rated_power_w != new.rated_power_w:
        diffs.append(f"power {old.rated_power_w:g} → {new.rated_power_w:g} W")
    if old.quantity != new.quantity:
        diffs.append(f"quantity {old.quantity} → {new.quantity}")
    if old.duty_cycle != new.duty_cycle:
        diffs.append(f"duty cycle {old.duty_cycle:.0%} → {new.duty_cycle:.0%}")
    if old.mode is not new.mode:
        diffs.append(f"{old.mode.value} → {new.mode.value}")
    if on_minutes_per_day(old) != on_minutes_per_day(new):
        diffs.append(
            f"on-time {_hours(on_minutes_per_day(old))} → {_hours(on_minutes_per_day(new))} a day"
        )
    if old.operating_days != new.operating_days:
        diffs.append(f"{_days(old)} → {_days(new)}")
    if old.flexible and new.flexible:
        a, b = old.flexible.allowed_window, new.flexible.allowed_window
        if (a.start_minute, a.end_minute) != (b.start_minute, b.end_minute):
            diffs.append(
                f"window {format_minute(a.start_minute)}-{format_minute(a.end_minute)} → "
                f"{format_minute(b.start_minute)}-{format_minute(b.end_minute)}"
            )
        if old.flexible.current_start_minute != new.flexible.current_start_minute:
            diffs.append(
                f"usual start {format_minute(old.flexible.current_start_minute)} → "
                f"{format_minute(new.flexible.current_start_minute)}"
            )
        if old.flexible.preferred_window != new.flexible.preferred_window:
            diffs.append("preferred window changed")
    if old.fixed_blocks != new.fixed_blocks:
        diffs.append("on-periods changed")
    if old.priority is not new.priority:
        diffs.append(f"priority {old.priority.value} → {new.priority.value}")
    if old.allow_simultaneous != new.allow_simultaneous:
        diffs.append("simultaneous use " + ("allowed" if new.allow_simultaneous else "not allowed"))
    return diffs


def describe_change(
    change: Change,
    appliances: Mapping[int, ApplianceSpec],
    tariff_names: Mapping[int, str],
    current_limit_kw: float | None,
) -> str:
    def name_of(appliance_id: int) -> str:
        spec = appliances.get(appliance_id)
        return f'"{spec.name}"' if spec else f"appliance #{appliance_id} (no longer exists)"

    match change:
        case AddAppliance(spec=spec):
            return f'Add "{spec.name}" ({appliance_summary(spec)})'
        case ReplaceAppliance(appliance_id=target, spec=spec):
            old = appliances.get(target)
            diffs = appliance_differences(old, spec) if old else ["settings replaced"]
            return f"Change {name_of(target)}: " + (", ".join(diffs) if diffs else "no differences")
        case RemoveAppliance(appliance_id=target):
            return f"Remove {name_of(target)}"
        case ChangeTariff(tariff_id=chosen):
            label = tariff_names.get(chosen)
            return f'Use tariff "{label}"' if label else f"Use tariff #{chosen} (no longer exists)"
        case SetLoadLimit(max_load_kw=value):
            before = f"{current_limit_kw:g} kW" if current_limit_kw is not None else "no limit"
            return f"Load limit {before} → {value:g} kW"
    raise AssertionError("unreachable: every change type is handled above")
