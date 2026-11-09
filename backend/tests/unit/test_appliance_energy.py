"""Hand-calculated examples for the rated-vs-average power formulas."""

from __future__ import annotations

import pytest

from powershift.calculation.appliance_energy import estimate_appliance
from powershift.domain.time_window import TimeWindow
from tests.factories import fixed_spec, flexible_schedule, flexible_spec


def test_refrigerator_always_on_with_duty_cycle() -> None:
    # 150 W x 1 x 0.4 = 60 W average; 24 h -> 1.44 kWh/day; 7 days -> 10.08 kWh/week
    estimate = estimate_appliance(fixed_spec())

    assert estimate.max_power_kw == pytest.approx(0.150)
    assert estimate.average_power_kw == pytest.approx(0.060)
    assert estimate.on_hours_per_day == pytest.approx(24)
    assert estimate.energy_per_operating_day_kwh == pytest.approx(1.44)
    assert estimate.energy_per_week_kwh == pytest.approx(10.08)


def test_quantity_multiplies_power() -> None:
    # 6 LED bulbs x 9 W, duty 1, 18:00-23:00 (5 h): 54 W -> 0.27 kWh/day
    lights = fixed_spec(
        rated_power_w=9, quantity=6, duty_cycle=1.0, fixed_blocks=(TimeWindow(1080, 1380),)
    )
    estimate = estimate_appliance(lights)

    assert estimate.max_power_kw == pytest.approx(0.054)
    assert estimate.energy_per_operating_day_kwh == pytest.approx(0.27)


def test_multiple_blocks_including_overnight_are_summed() -> None:
    # 1 kW, 06:00-07:00 (1 h) + 22:00-01:00 (3 h) = 4 h -> 4 kWh
    heater = fixed_spec(
        rated_power_w=1000,
        duty_cycle=1.0,
        fixed_blocks=(TimeWindow(360, 420), TimeWindow(1320, 60)),
    )
    assert estimate_appliance(heater).energy_per_operating_day_kwh == pytest.approx(4.0)


def test_flexible_run_uses_run_duration_and_operating_days() -> None:
    # 2000 W x 0.5 = 1 kW avg; 90 min -> 1.5 kWh per run; 3 days -> 4.5 kWh/week
    estimate = estimate_appliance(flexible_spec())

    assert estimate.max_power_kw == pytest.approx(2.0)
    assert estimate.average_power_kw == pytest.approx(1.0)
    assert estimate.energy_per_operating_day_kwh == pytest.approx(1.5)
    assert estimate.energy_per_week_kwh == pytest.approx(4.5)


def test_max_power_ignores_duty_cycle() -> None:
    # Load limits care about the worst instant, not the average.
    spec = flexible_spec(duty_cycle=0.1, flexible=flexible_schedule())
    assert estimate_appliance(spec).max_power_kw == pytest.approx(2.0)
