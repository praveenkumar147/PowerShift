"""Per-appliance power and energy estimates.

Rated power vs. estimated actual consumption
--------------------------------------------
A label saying "150 W" is the most the appliance draws while working at full
power. A fridge compressor switches on and off, so over an hour it draws 150 W
only part of the time. The duty cycle is that fraction:

    max power (kW)        = rated W x quantity / 1000             (worst case, for load limits)
    average power (kW)    = rated W x quantity x duty cycle / 1000 (for energy and cost)
    energy per day (kWh)  = average power (kW) x hours switched on

kW is power (a rate, like speed); kWh is energy (an amount, like distance).
A 2 kW heater running for 30 minutes uses 1 kWh.
"""

from __future__ import annotations

from dataclasses import dataclass

from powershift.domain.appliance import ApplianceMode, ApplianceSpec

WATTS_PER_KILOWATT = 1000
MINUTES_PER_HOUR = 60


@dataclass(frozen=True, slots=True)
class ApplianceEstimate:
    max_power_kw: float
    average_power_kw: float
    on_hours_per_day: float
    energy_per_operating_day_kwh: float
    energy_per_week_kwh: float


def max_power_kw(spec: ApplianceSpec) -> float:
    return spec.rated_power_w * spec.quantity / WATTS_PER_KILOWATT


def average_power_kw(spec: ApplianceSpec) -> float:
    return max_power_kw(spec) * spec.duty_cycle


def on_minutes_per_day(spec: ApplianceSpec) -> int:
    if spec.mode is ApplianceMode.FIXED:
        return sum(block.length_minutes for block in spec.fixed_blocks)
    return spec.flexible.run_duration_minutes if spec.flexible else 0


def estimate_appliance(spec: ApplianceSpec) -> ApplianceEstimate:
    on_hours = on_minutes_per_day(spec) / MINUTES_PER_HOUR
    daily_kwh = average_power_kw(spec) * on_hours
    return ApplianceEstimate(
        max_power_kw=max_power_kw(spec),
        average_power_kw=average_power_kw(spec),
        on_hours_per_day=on_hours,
        energy_per_operating_day_kwh=daily_kwh,
        energy_per_week_kwh=daily_kwh * len(spec.operating_days),
    )
