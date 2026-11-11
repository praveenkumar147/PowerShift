"""Scenario changes are applied to COPIES; every rule is checked here without a database."""

from __future__ import annotations

from dataclasses import replace

from powershift.domain.appliance import ApplianceMode
from powershift.domain.time_window import TimeWindow
from powershift.simulation.describe import appliance_differences, describe_change
from powershift.simulation.scenario import (
    AddAppliance,
    ChangeTariff,
    RemoveAppliance,
    ReplaceAppliance,
    SetLoadLimit,
    apply_changes,
)
from tests.factories import fixed_spec, flexible_schedule, flexible_spec

FRIDGE = fixed_spec(name="Refrigerator")
WASHER = flexible_spec(name="Washing machine")
HOME = [(1, FRIDGE), (2, WASHER)]
AC = fixed_spec(name="Air conditioner", rated_power_w=1500, duty_cycle=0.6)


def test_changes_never_modify_the_original_household() -> None:
    original = list(HOME)
    apply_changes(
        HOME,
        5.0,
        [AddAppliance(AC), RemoveAppliance(1), ReplaceAppliance(2, replace(WASHER, quantity=3))],
    )
    assert original == HOME
    assert HOME[1][1].quantity == 1  # specs are immutable; the replacement is a new object


def test_add_gives_negative_ids_that_cannot_clash_with_real_ones() -> None:
    inputs, errors = apply_changes(
        HOME, None, [AddAppliance(AC), AddAppliance(replace(AC, name="AC 2"))]
    )
    assert errors == {}
    assert [i for i, _ in inputs.appliances] == [1, 2, -1, -2]


def test_replace_and_remove_target_one_appliance() -> None:
    bigger = replace(WASHER, rated_power_w=3000)
    inputs, errors = apply_changes(HOME, None, [ReplaceAppliance(2, bigger), RemoveAppliance(1)])
    assert errors == {}
    assert inputs.appliances == [(2, bigger)]


def test_tariff_and_load_limit_changes() -> None:
    inputs, _ = apply_changes(HOME, 5.0, [ChangeTariff(7), SetLoadLimit(8.0)])
    assert inputs.tariff_id == 7 and inputs.load_limit_kw == 8.0
    unchanged, _ = apply_changes(HOME, 5.0, [])
    assert unchanged.tariff_id is None and unchanged.load_limit_kw == 5.0


def test_unknown_or_already_removed_appliances_are_reported_by_change_index() -> None:
    _, errors = apply_changes(
        HOME, None, [RemoveAppliance(99), RemoveAppliance(1), RemoveAppliance(1)]
    )
    assert set(errors) == {"changes.0.appliance_id", "changes.2.appliance_id"}
    _, errors = apply_changes(HOME, None, [RemoveAppliance(1), ReplaceAppliance(1, FRIDGE)])
    assert set(errors) == {"changes.1.appliance_id"}


def test_inconsistent_appliances_are_reported_with_field_paths() -> None:
    impossible = flexible_spec(
        name="Oven",
        flexible=flexible_schedule(run_duration_minutes=180, allowed_window=TimeWindow(1320, 1440)),
    )
    _, errors = apply_changes(HOME, None, [AddAppliance(impossible)])
    assert "changes.0.appliance.flexible.run_duration_minutes" in errors
    assert errors["changes.0.appliance.flexible.run_duration_minutes"].startswith(
        "A 180-minute run"
    )


def test_name_clashes_are_rejected_case_insensitively() -> None:
    _, errors = apply_changes(HOME, None, [AddAppliance(replace(AC, name="REFRIGERATOR"))])
    assert errors == {
        "changes.0.appliance.name": "Another appliance in this scenario already has this name."
    }
    _, errors = apply_changes(HOME, None, [AddAppliance(AC), AddAppliance(AC)])
    assert "changes.0.appliance.name" in errors and "changes.1.appliance.name" in errors
    # Renaming into a name freed by removal is fine.
    _, errors = apply_changes(
        HOME, None, [RemoveAppliance(1), AddAppliance(replace(AC, name="Refrigerator"))]
    )
    assert errors == {}


def test_a_replaced_appliance_may_keep_its_own_name() -> None:
    _, errors = apply_changes(HOME, None, [ReplaceAppliance(1, replace(FRIDGE, quantity=2))])
    assert errors == {}


def test_differences_list_exactly_what_changed() -> None:
    new = replace(WASHER, rated_power_w=2400, operating_days=(0,), duty_cycle=0.7)
    assert appliance_differences(WASHER, new) == [
        "power 2000 → 2400 W",
        "duty cycle 50% → 70%",
        "3 days a week → 1 day a week",
    ]
    assert appliance_differences(WASHER, WASHER) == []
    assert ApplianceMode.FLEXIBLE in {WASHER.mode}


def test_descriptions_are_generated_from_the_data() -> None:
    by_id = {1: FRIDGE, 2: WASHER}
    describe = lambda change, limit=5.0: describe_change(change, by_id, {7: "Night saver"}, limit)  # noqa: E731
    assert (
        describe(AddAppliance(AC))
        == 'Add "Air conditioner" (1.5 kW, fixed, 24 h on, 7 days a week)'
    )
    assert describe(RemoveAppliance(1)) == 'Remove "Refrigerator"'
    assert describe(RemoveAppliance(9)) == "Remove appliance #9 (no longer exists)"
    assert describe(ChangeTariff(7)) == 'Use tariff "Night saver"'
    assert describe(SetLoadLimit(8)) == "Load limit 5 kW → 8 kW"
    assert describe(SetLoadLimit(8), None) == "Load limit no limit → 8 kW"
    assert describe(ReplaceAppliance(2, WASHER)) == 'Change "Washing machine": no differences'
