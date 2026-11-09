from __future__ import annotations

from dataclasses import replace
from decimal import Decimal as D

from powershift.domain.tariff import DayType, Slab, TouPeriod, validate_tariff
from powershift.domain.time_window import TimeWindow
from tests.factories import flat_tariff, slab_tariff, tou_tariff


def test_valid_tariffs_pass() -> None:
    assert validate_tariff(flat_tariff()) == {}
    assert validate_tariff(tou_tariff()) == {}
    assert validate_tariff(slab_tariff()) == {}


def test_flat_tariff_needs_a_rate() -> None:
    assert "flat_rate_per_kwh" in validate_tariff(replace(flat_tariff(), flat_rate_per_kwh=None))


def test_type_specific_fields_must_match_type() -> None:
    errors = validate_tariff(replace(flat_tariff(), slabs=slab_tariff().slabs))
    assert "slabs" in errors
    errors = validate_tariff(replace(slab_tariff(), flat_rate_per_kwh=D("4")))
    assert "flat_rate_per_kwh" in errors


def test_tou_gap_is_reported_with_its_time() -> None:
    periods = tou_tariff().tou_periods[:-1]  # drop 22:00-24:00
    assert validate_tariff(tou_tariff(periods))["tou_periods"] == "No price is set for 22:00."


def test_tou_overlap_is_reported() -> None:
    periods = (*tou_tariff().tou_periods, TouPeriod(TimeWindow(1200, 1260), DayType.ALL, D(9)))
    assert validate_tariff(tou_tariff(periods))["tou_periods"] == "Periods overlap at 20:00."


def test_tou_periods_may_wrap_midnight() -> None:
    periods = (
        TouPeriod(TimeWindow(1320, 360), DayType.ALL, D(3)),  # 22:00-06:00
        TouPeriod(TimeWindow(360, 1320), DayType.ALL, D(6)),
    )
    assert validate_tariff(tou_tariff(periods)) == {}


def test_weekday_and_weekend_sets_must_each_cover_the_day() -> None:
    weekday_only = tuple(replace(p, day_type=DayType.WEEKDAY) for p in tou_tariff().tou_periods)
    weekend_partial = (TouPeriod(TimeWindow(0, 720), DayType.WEEKEND, D(4)),)

    message = validate_tariff(tou_tariff(weekday_only + weekend_partial))["tou_periods"]

    assert message == "No price is set for 12:00 on weekends."


def test_every_day_periods_cannot_mix_with_weekday_periods() -> None:
    periods = (*tou_tariff().tou_periods, TouPeriod(TimeWindow(0, 1440), DayType.WEEKEND, D(4)))
    assert "either" in validate_tariff(tou_tariff(periods))["tou_periods"]


def test_slab_limits_must_increase_and_only_last_is_open() -> None:
    def errors(*slabs: Slab) -> dict[str, str]:
        return validate_tariff(replace(slab_tariff(), slabs=slabs))

    assert "slabs.1.up_to_kwh" in errors(Slab(D(100), D(3)), Slab(D(50), D(4)), Slab(None, D(5)))
    assert "slabs.0.up_to_kwh" in errors(Slab(None, D(3)), Slab(None, D(4)))
    assert "slabs.1.up_to_kwh" in errors(Slab(D(100), D(3)), Slab(D(200), D(4)))
    assert errors() == {"slabs": "Add at least one slab."}
    assert errors(Slab(None, D(3))) == {}  # a single open slab is a flat rate in disguise


def test_day_type_matching() -> None:
    assert DayType.WEEKDAY.applies_to(4) and not DayType.WEEKDAY.applies_to(5)
    assert DayType.WEEKEND.applies_to(6) and not DayType.WEEKEND.applies_to(0)
    assert all(DayType.ALL.applies_to(d) for d in range(7))
