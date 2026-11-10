"""Substep L and diagnostics: explanations come from measured differences;
infeasible problems get a specific cause."""

from __future__ import annotations

from powershift.domain.time_window import format_minute
from powershift.optimization.diagnose import diagnose
from powershift.optimization.explain import explain
from powershift.optimization.problem import build_problem
from tests.factories import flat_tariff, tou_tariff
from tests.optimization.helpers import fixed, flex, hhmm, numbered, window

# TOU prices: 00-06 @3, 06-18 @5, 18-22 @8, 22-24 @3.


def codes(reasons: list) -> list[str]:  # type: ignore[type-arg]
    return [r.code for r in reasons]


def test_move_to_cheaper_hours_is_explained_with_the_actual_prices() -> None:
    home = numbered(flex("Washer", 2000, 60, window("06:00", "23:00"), "19:00"))
    reasons = explain(home, {1: hhmm("16:00")}, tou_tariff(), None, proven_optimal=True)[1]
    assert codes(reasons) == ["cheaper_time"]
    assert "8.00 → 5.00 per kWh" in reasons[0].text


def test_no_price_reason_under_a_flat_tariff() -> None:
    tv = fixed("TV", 1500, (window("19:00", "21:00"),))
    home = numbered(tv, flex("Washer", 2000, 60, window("06:00", "23:00"), "19:00"))
    reasons = explain(home, {2: hhmm("21:00")}, flat_tariff(), None, proven_optimal=True)[2]
    assert codes(reasons) == ["avoids_overlap", "lower_demand"]
    assert "TV" in reasons[0].text
    assert "from 3.50 to 2.00 kW" in reasons[1].text


def test_separation_of_not_simultaneous_appliances_is_explained_once() -> None:
    washer = flex("Washer", 2000, 90, window("06:00", "23:00"), "19:00", allow_simultaneous=False)
    dryer = flex("Dryer", 2000, 60, window("06:00", "23:00"), "20:00", allow_simultaneous=False)
    reasons = explain(
        numbered(washer, dryer), {1: hhmm("18:00"), 2: hhmm("20:00")}, None, None, True
    )

    assert codes(reasons[1]) == ["separated", "lower_demand"]  # not also "avoids_overlap"
    assert "Dryer" in reasons[1][0].text
    assert codes(reasons[2]) == ["unchanged"]
    assert "No other start time gives a better result" in reasons[2][0].text


def test_limit_violation_fixed_by_the_move_is_explained() -> None:
    oven = fixed("Oven", 2500, (window("19:00", "20:00"),))
    home = numbered(oven, flex("Heater", 2000, 60, window("17:00", "23:00"), "19:00"))
    reasons = explain(home, {2: hhmm("20:00")}, None, limit_kw=4, proven_optimal=True)[2]
    assert "limit_respected" in codes(reasons)
    text = next(r.text for r in reasons if r.code == "limit_respected")
    assert "reached 4.50 kW, above your 4 kW limit" in text and "2.00 kW" in text


def test_costlier_move_and_new_overlap_are_disclosed_honestly() -> None:
    dryer = fixed("Dryer", 1500, (window("19:00", "20:00"),))
    home = numbered(dryer, flex("Washer", 2000, 60, window("06:00", "23:00"), "16:00"))
    reasons = explain(home, {2: hhmm("19:00")}, tou_tariff(), None, proven_optimal=False)[2]
    assert codes(reasons) == ["costlier_time", "new_overlap", "higher_demand"]


def test_preferred_window_and_time_format() -> None:
    washer = flex(
        "Washer", 2000, 60, window("06:00", "23:00"), "19:00", preferred=window("14:00", "17:00")
    )
    twelve = lambda m: format_minute(m, twelve_hour=True)  # noqa: E731
    kept = explain(numbered(washer), {1: hhmm("16:00")}, tou_tariff(), None, True, twelve)[1]
    assert kept[-1].code == "preferred_kept" and "2:00 PM-5:00 PM" in kept[-1].text
    missed = explain(numbered(washer), {1: hhmm("10:00")}, tou_tariff(), None, True)[1]
    assert missed[-1].code == "outside_preferred"


def test_unchanged_without_proof_makes_no_optimality_claim() -> None:
    home = numbered(flex("Washer", 2000, 60, window("06:00", "23:00"), "19:00"))
    reasons = explain(home, {1: hhmm("19:00")}, None, None, proven_optimal=False)[1]
    assert reasons[0].text == "Kept at its usual time."


# --- Diagnostics -------------------------------------------------------------------


def diagnosis(*specs, limit: float | None):  # type: ignore[no-untyped-def]
    found = diagnose(build_problem(numbered(*specs), None, limit))
    return {d.code: d.message for d in found}


def test_fixed_load_alone_over_the_limit() -> None:
    oven = fixed("Oven", 3500, (window("19:00", "20:00"),))
    lamp = flex("Lamp", 10, 60, window("00:00", "00:00"), "10:00")
    found = diagnosis(oven, lamp, limit=3)
    assert "fixed_load_over_limit" in found
    assert (
        "19:00-20:00" in found["fixed_load_over_limit"]
        and "3.50 kW" in found["fixed_load_over_limit"]
    )


def test_single_appliance_that_cannot_fit_under_the_limit() -> None:
    tv = fixed("TV", 1000, (window("18:00", "22:00"),))
    heater = flex("Heater", 2500, 60, window("18:00", "22:00"), "19:00")
    found = diagnosis(tv, heater, limit=3)
    assert (
        "Heater (2.50 kW) cannot run anywhere in its window 18:00-22:00"
        in found["appliance_cannot_fit"]
    )
    assert "3.50 kW" in found["limit_too_low"]  # smallest limit that would work


def test_limit_too_low_reports_the_smallest_workable_limit() -> None:
    a = flex("A", 2000, 120, window("18:00", "20:00"), "18:00")
    b = flex("B", 2000, 120, window("18:00", "20:00"), "18:00")
    found = diagnosis(a, b, limit=3)
    assert set(found) == {"limit_too_low"}
    assert "lowest peak any schedule can reach is 4.00 kW" in found["limit_too_low"]


def test_not_simultaneous_rule_blocking() -> None:
    a = flex("Washer", 500, 120, window("10:00", "12:00"), "10:00", allow_simultaneous=False)
    b = flex("Dryer", 500, 120, window("10:00", "12:00"), "10:00", allow_simultaneous=False)
    found = diagnosis(a, b, limit=None)
    assert set(found) == {"not_simultaneous_blocks"}
    assert "Washer, Dryer" in found["not_simultaneous_blocks"]
