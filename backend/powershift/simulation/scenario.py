"""What-if scenarios: changes applied to COPIES of the household.

A scenario never stores or edits real data. It is a list of changes; running it
builds a new in-memory list of appliances (plus a tariff and a load limit) from the
current household, applies the changes to that copy, and analyses the copy.
Domain specs are immutable, and nothing here imports the database, so a scenario
cannot write to the real tables.

New appliances get NEGATIVE ids (-1, -2, ...) so they can never clash with a real
appliance id.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from powershift.domain.appliance import ApplianceSpec, validate_appliance

Appliances = Sequence[tuple[int, ApplianceSpec]]


@dataclass(frozen=True, slots=True)
class AddAppliance:
    spec: ApplianceSpec


@dataclass(frozen=True, slots=True)
class ReplaceAppliance:
    appliance_id: int
    spec: ApplianceSpec


@dataclass(frozen=True, slots=True)
class RemoveAppliance:
    appliance_id: int


@dataclass(frozen=True, slots=True)
class ChangeTariff:
    tariff_id: int


@dataclass(frozen=True, slots=True)
class SetLoadLimit:
    max_load_kw: float


Change = AddAppliance | ReplaceAppliance | RemoveAppliance | ChangeTariff | SetLoadLimit


@dataclass(frozen=True, slots=True)
class ScenarioInputs:
    """The household a scenario produces, ready for the calculation engines."""

    appliances: list[tuple[int, ApplianceSpec]]
    tariff_id: int | None
    """None means "keep the active tariff"."""
    load_limit_kw: float | None


def apply_changes(
    appliances: Appliances,
    load_limit_kw: float | None,
    changes: Sequence[Change],
) -> tuple[ScenarioInputs, dict[str, str]]:
    """Applies changes to copies. Returns the result and {field path: message} for
    changes that cannot apply (unknown appliance, inconsistent appliance, name clash)."""
    errors: dict[str, str] = {}
    current = list(appliances)
    existing_ids = {i for i, _ in appliances}
    next_new_id = -1
    tariff_id: int | None = None
    limit = load_limit_kw

    for index, change in enumerate(changes):
        key = f"changes.{index}"
        match change:
            case AddAppliance(spec=spec):
                problems = validate_appliance(spec)
                for field, message in problems.items():
                    errors[f"{key}.appliance.{field}"] = message
                current.append((next_new_id, spec))
                next_new_id -= 1
            case ReplaceAppliance(appliance_id=target, spec=spec):
                if target not in existing_ids or all(i != target for i, _ in current):
                    errors[f"{key}.appliance_id"] = (
                        "This appliance no longer exists or was already removed by another change."
                    )
                    continue
                for field, message in validate_appliance(spec).items():
                    errors[f"{key}.appliance.{field}"] = message
                current = [(i, spec if i == target else s) for i, s in current]
            case RemoveAppliance(appliance_id=target):
                if target not in existing_ids or all(i != target for i, _ in current):
                    errors[f"{key}.appliance_id"] = (
                        "This appliance no longer exists or was already removed by another change."
                    )
                    continue
                current = [(i, s) for i, s in current if i != target]
            case ChangeTariff(tariff_id=chosen):
                tariff_id = chosen
            case SetLoadLimit(max_load_kw=value):
                limit = value

    # Names must stay unique (ignoring case) in the final scenario household.
    counts: dict[str, int] = {}
    for _, spec in current:
        counts[spec.name.lower()] = counts.get(spec.name.lower(), 0) + 1
    for index, change in enumerate(changes):
        if (
            isinstance(change, AddAppliance | ReplaceAppliance)
            and counts.get(change.spec.name.lower(), 0) > 1
        ):
            errors[f"changes.{index}.appliance.name"] = (
                "Another appliance in this scenario already has this name."
            )

    return ScenarioInputs(current, tariff_id, limit), errors
