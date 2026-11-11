"""Simulation Lab end to end. The sample household has 6 fixed and 3 flexible
appliances (washing machine, dishwasher, water heater), a time-of-use tariff and a 5 kW limit."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.factories import HOUSEHOLD_PAYLOAD, fixed_payload, flexible_payload
from tests.integration.test_tariffs_api import FLAT

REAL_TABLES = [
    "household",
    "appliances",
    "appliance_operating_days",
    "appliance_usage_blocks",
    "appliance_flex_constraints",
    "tariffs",
    "tariff_periods",
    "tariff_slabs",
    "tariff_charges",
]


@pytest.fixture
def sample(client: TestClient) -> TestClient:
    assert client.post("/api/demo").status_code == 201
    return client


def appliance(client: TestClient, name: str) -> dict[str, Any]:
    found = next(a for a in client.get("/api/appliances").json() if a["name"] == name)
    return dict(found)


def as_input(appliance_json: dict[str, Any], **changes: Any) -> dict[str, Any]:
    body = {k: v for k, v in appliance_json.items() if k not in ("id", "estimates", "warnings")}
    body.update(changes)
    return body


STUDY_AC = fixed_payload(
    name="Study AC",
    category="cooling",
    rated_power_w=1500,
    duty_cycle=0.6,
    fixed_blocks=[{"start_minute": 1320, "end_minute": 360}],
)


def scenario(
    name: str = "Add AC", changes: list[dict[str, Any]] | None = None, **extra: Any
) -> dict[str, Any]:
    return {"name": name, "changes": changes if changes is not None else [], **extra}


def create(client: TestClient, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/simulations", json=body)
    assert response.status_code == 201, response.json()
    created: dict[str, Any] = response.json()
    return created


def run(client: TestClient, scenario_id: int) -> dict[str, Any]:
    response = client.post(f"/api/simulations/{scenario_id}/run")
    assert response.status_code == 201, response.json()
    result: dict[str, Any] = response.json()
    return result


def real_data(client: TestClient) -> dict[str, list[tuple[Any, ...]]]:
    """Every row of every table holding the user's real data."""
    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        return {
            t: [tuple(r) for r in session.execute(text(f"SELECT * FROM {t} ORDER BY 1"))]
            for t in REAL_TABLES
        }


# --- The core guarantee: isolation ---------------------------------------------------


def test_scenarios_never_change_real_data(sample: TestClient) -> None:
    before = real_data(sample)
    washer = appliance(sample, "Washing machine")
    other_tariff = sample.post("/api/tariffs", json=FLAT).json()
    before = real_data(sample)  # includes the second tariff, created on purpose above
    history_before = sample.get("/api/optimization/history").json()

    created = create(
        sample,
        scenario(
            "Everything at once",
            [
                {"type": "add_appliance", "appliance": STUDY_AC},
                {
                    "type": "replace_appliance",
                    "appliance_id": washer["id"],
                    "appliance": as_input(washer, rated_power_w=3500),
                },
                {"type": "remove_appliance", "appliance_id": appliance(sample, "Television")["id"]},
                {"type": "change_tariff", "tariff_id": other_tariff["id"]},
                {"type": "set_load_limit", "max_load_kw": 9},
            ],
            priority="cost",
        ),
    )
    run(sample, created["id"])
    sample.put(
        f"/api/simulations/{created['id']}",
        json=scenario("Everything at once", [], priority="peak"),
    )
    run(sample, created["id"])
    sample.delete(f"/api/simulations/{created['id']}")

    assert real_data(sample) == before
    assert sample.get("/api/optimization/history").json() == history_before


def test_scenario_appliances_never_appear_in_the_real_household(sample: TestClient) -> None:
    created = create(sample, scenario(changes=[{"type": "add_appliance", "appliance": STUDY_AC}]))
    result = run(sample, created["id"])

    assert "Study AC" not in [a["name"] for a in sample.get("/api/appliances").json()]
    assert result["scenario"]["monthly_kwh"] > result["baseline"]["monthly_kwh"]


# --- Calculations ---------------------------------------------------------------------


def test_baseline_matches_the_normal_energy_figures(sample: TestClient) -> None:
    today = date.today()
    bill = sample.get(f"/api/energy/bill?year={today.year}&month={today.month}").json()
    peak = sample.get("/api/peak-load/analysis").json()

    result = run(sample, create(sample, scenario("No changes", priority="peak"))["id"])

    assert result["baseline"]["monthly_bill"] == bill["total"]
    assert result["baseline"]["monthly_kwh"] == pytest.approx(bill["total_kwh"], abs=0.001)
    assert result["baseline"]["peak_kw"] == pytest.approx(peak["peak_kw"], abs=0.001)
    # No changes: the scenario at usual times IS the baseline.
    assert result["scenario"] == result["baseline"]
    assert (
        result["kwh_change"] == 0 and result["bill_change"] == 0 and result["peak_change_kw"] <= 0
    )


def test_adding_an_appliance_costs_more_and_says_how_much(sample: TestClient) -> None:
    result = run(
        sample,
        create(sample, scenario(changes=[{"type": "add_appliance", "appliance": STUDY_AC}]))["id"],
    )

    # 1.5 kW x 0.6 duty x 8 h x 30 days (22:00-06:00) = 216 kWh in a 30-day month.
    assert result["kwh_change"] == pytest.approx(0.9 * 8 * date_days(), abs=0.01)
    assert result["bill_change"] > 0
    assert result["change_descriptions"] == [
        'Add "Study AC" (1.5 kW, fixed, 8 h on, 7 days a week)'
    ]
    assert result["schedule_valid"] is True
    # Optimising the scenario can only improve on the scenario's own usual-times schedule.
    assert result["optimized"]["monthly_bill"] <= result["scenario"]["monthly_bill"]
    assert result["optimization_savings"] >= 0
    assert result["optimized_bill_change"] == pytest.approx(
        result["optimized"]["monthly_bill"] - result["baseline"]["monthly_bill"], abs=0.005
    )


def date_days() -> int:
    import calendar

    today = date.today()
    return calendar.monthrange(today.year, today.month)[1]


def test_reducing_washing_machine_use_saves_energy_and_money(sample: TestClient) -> None:
    washer = appliance(sample, "Washing machine")  # sample: Mon, Thu, Sat
    changes = [
        {
            "type": "replace_appliance",
            "appliance_id": washer["id"],
            "appliance": as_input(washer, operating_days=[0, 3]),
        }
    ]
    result = run(sample, create(sample, scenario("Wash less", changes, priority="peak"))["id"])

    assert result["kwh_change"] < 0 and result["bill_change"] < 0
    assert result["change_descriptions"] == [
        'Change "Washing machine": 3 days a week → 2 days a week'
    ]


def test_a_different_tariff_changes_the_bill_but_not_the_energy(sample: TestClient) -> None:
    flat = sample.post("/api/tariffs", json=FLAT).json()
    changes = [{"type": "change_tariff", "tariff_id": flat["id"]}]
    result = run(sample, create(sample, scenario("Flat tariff", changes))["id"])

    assert result["kwh_change"] == 0
    assert result["bill_change"] != 0
    assert result["tariff"]["name"] == "Flat" and result["tariff"]["tariff_type"] == "flat"
    assert any("not time-of-use" in n for n in result["notes"])
    assert result["optimization_savings"] == 0  # flat prices: timing cannot save money


def test_load_limit_too_low_for_the_scenario_is_infeasible_and_explained(
    sample: TestClient,
) -> None:
    result = run(
        sample,
        create(sample, scenario("Tight limit", [{"type": "set_load_limit", "max_load_kw": 2.5}]))[
            "id"
        ],
    )

    assert result["status"] == "INFEASIBLE" and result["schedule_valid"] is False
    assert result["optimized"] is None and result["optimization_savings"] is None
    assert (
        result["optimization_note"]
        == "No valid schedule exists for this scenario (see the reasons below)."
    )
    assert {d["code"] for d in result["diagnostics"]} >= {"appliance_cannot_fit"}
    assert (
        result["scenario"]["minutes_over_limit"] > 0
    )  # the usual-times numbers are still reported
    assert result["items"] == []


def test_a_higher_limit_can_lower_the_peak_goal_results(sample: TestClient) -> None:
    low = run(
        sample,
        create(
            sample,
            scenario("Limit 4", [{"type": "set_load_limit", "max_load_kw": 4}], priority="cost"),
        )["id"],
    )
    high = run(
        sample,
        create(
            sample,
            scenario("Limit 9", [{"type": "set_load_limit", "max_load_kw": 9}], priority="cost"),
        )["id"],
    )
    # More room can never make the cheapest valid schedule more expensive.
    assert high["optimized"]["monthly_bill"] <= low["optimized"]["monthly_bill"]


def test_scheduling_priorities_can_be_compared_on_identical_data(sample: TestClient) -> None:
    results = {
        p: run(sample, create(sample, scenario(f"Goal {p}", priority=p))["id"])
        for p in ("cost", "balanced", "peak")
    }
    bills = [results[p]["optimized"]["monthly_bill"] for p in ("cost", "balanced", "peak")]
    peaks = [results[p]["optimized"]["peak_kw"] for p in ("cost", "balanced", "peak")]
    assert bills == sorted(bills)  # cost <= balanced <= peak
    assert peaks == sorted(peaks, reverse=True)  # peak <= balanced <= cost
    assert {r["scenario"]["monthly_bill"] for r in results.values()} == {
        results["cost"]["scenario"]["monthly_bill"]
    }


def test_scenarios_that_cannot_be_optimised_still_report_the_comparison(client: TestClient) -> None:
    client.put("/api/household", json=HOUSEHOLD_PAYLOAD)
    client.post("/api/appliances", json=fixed_payload())
    result = run(client, create(client, scenario("Nothing flexible", priority="peak"))["id"])

    assert result["status"] is None and result["schedule_valid"] is False
    assert "no flexible appliances" in result["optimization_note"]
    assert result["optimized"] is None
    assert (
        result["baseline"]["monthly_bill"] is None
    )  # no tariff: costs unavailable, energy still shown
    assert result["baseline"]["monthly_kwh"] > 0


def test_cost_goal_without_a_tariff_is_not_attempted_but_explained(client: TestClient) -> None:
    client.post("/api/appliances", json=flexible_payload())
    result = run(client, create(client, scenario("Cost, no tariff", priority="cost"))["id"])
    assert result["status"] is None
    assert "without an active tariff" in result["optimization_note"]


# --- Scenario management ---------------------------------------------------------------


def test_scenarios_round_trip_and_are_listed_by_name(sample: TestClient) -> None:
    washer = appliance(sample, "Washing machine")
    body = scenario(
        "Zebra",
        [
            {
                "type": "replace_appliance",
                "appliance_id": washer["id"],
                "appliance": as_input(washer, quantity=2),
            }
        ],
        description="  two washers  ",
        priority="cost",
        balance_weight=30,
    )
    created = create(sample, body)
    create(sample, scenario("Alpha"))

    assert created["description"] == "two washers" and created["latest_result"] is None
    assert created["changes"][0]["appliance"]["quantity"] == 2
    assert sample.get(f"/api/simulations/{created['id']}").json() == created
    assert [s["name"] for s in sample.get("/api/simulations").json()] == ["Alpha", "Zebra"]


def test_results_are_stored_and_listed_newest_first(sample: TestClient) -> None:
    created = create(sample, scenario())
    first, second = run(sample, created["id"]), run(sample, created["id"])

    assert first["id"] < second["id"]
    assert [r["id"] for r in sample.get(f"/api/simulations/{created['id']}/results").json()] == [
        second["id"],
        first["id"],
    ]
    assert (
        sample.get(f"/api/simulations/{created['id']}").json()["latest_result"]["id"]
        == second["id"]
    )


def test_results_are_reproducible(sample: TestClient) -> None:
    created = create(sample, scenario(changes=[{"type": "add_appliance", "appliance": STUDY_AC}]))
    a, b = run(sample, created["id"]), run(sample, created["id"])
    keys = (
        "baseline",
        "scenario",
        "optimized",
        "items",
        "kwh_change",
        "bill_change",
        "optimization_savings",
    )
    assert {k: a[k] for k in keys} == {k: b[k] for k in keys}


def test_editing_a_scenario_marks_its_result_out_of_date(sample: TestClient) -> None:
    created = create(sample, scenario())
    run(sample, created["id"])
    assert sample.get(f"/api/simulations/{created['id']}").json()["result_is_stale"] is False

    sample.put(f"/api/simulations/{created['id']}", json=scenario(priority="peak"))
    assert sample.get(f"/api/simulations/{created['id']}").json()["result_is_stale"] is True

    run(sample, created["id"])
    assert sample.get(f"/api/simulations/{created['id']}").json()["result_is_stale"] is False


def test_deleting_a_scenario_deletes_its_results(sample: TestClient) -> None:
    created = create(sample, scenario())
    run(sample, created["id"])

    assert sample.delete(f"/api/simulations/{created['id']}").status_code == 204

    assert sample.get(f"/api/simulations/{created['id']}").status_code == 404
    with sample.app.state.session_factory() as session:  # type: ignore[attr-defined]
        assert session.execute(text("SELECT COUNT(*) FROM simulation_results")).scalar() == 0


def test_missing_scenarios_are_404(client: TestClient) -> None:
    assert client.get("/api/simulations/9").status_code == 404
    assert client.put("/api/simulations/9", json=scenario()).status_code == 404
    assert client.delete("/api/simulations/9").status_code == 404
    assert client.post("/api/simulations/9/run").status_code == 404
    assert client.get("/api/simulations/9/results").status_code == 404


# --- Validation ---------------------------------------------------------------------------


def test_duplicate_scenario_names_conflict_regardless_of_case(sample: TestClient) -> None:
    create(sample, scenario("Hot summer"))
    response = sample.post("/api/simulations", json=scenario("HOT SUMMER"))
    assert response.status_code == 409 and "name" in response.json()["error"]["fields"]
    # A scenario may keep its own name when edited.
    created = sample.get("/api/simulations").json()[0]
    assert (
        sample.put(
            f"/api/simulations/{created['id']}", json=scenario("Hot summer", priority="peak")
        ).status_code
        == 200
    )


def test_invalid_changes_are_rejected_with_field_paths_and_not_saved(sample: TestClient) -> None:
    too_long = flexible_payload(name="Slow oven")
    too_long["flexible"].update(
        run_duration_minutes=180,
        earliest_start_minute=1320,
        latest_end_minute=1440,
        current_start_minute=1320,
    )
    cases = {
        "changes.0.appliance_id": [{"type": "remove_appliance", "appliance_id": 999}],
        "changes.0.appliance.flexible.run_duration_minutes": [
            {"type": "add_appliance", "appliance": too_long}
        ],
        "changes.0.appliance.name": [
            {"type": "add_appliance", "appliance": fixed_payload(name="refrigerator")}
        ],
        "changes": [{"type": "change_tariff", "tariff_id": 999}],
    }
    for field, changes in cases.items():
        response = sample.post("/api/simulations", json=scenario("Bad", changes))
        assert response.status_code == 422, field
        assert field in response.json()["error"]["fields"], response.json()
    assert sample.get("/api/simulations").json() == []


@pytest.mark.parametrize(
    "body",
    [
        scenario("Bad type", [{"type": "teleport"}]),
        scenario("Limit", [{"type": "set_load_limit", "max_load_kw": 0}]),
        scenario("   "),
        scenario("Goal", priority="magic"),
        scenario("Weight", balance_weight=101),
        scenario("Many", [{"type": "set_load_limit", "max_load_kw": 5}] * 31),
        {**scenario("Extra"), "unexpected": 1},
    ],
)
def test_request_validation(client: TestClient, body: dict[str, Any]) -> None:
    assert client.post("/api/simulations", json=body).status_code == 422


def test_a_scenario_that_no_longer_fits_the_household_is_reported_when_run(
    sample: TestClient,
) -> None:
    washer = appliance(sample, "Washing machine")
    created = create(
        sample,
        scenario(
            "Stale base",
            [
                {
                    "type": "replace_appliance",
                    "appliance_id": washer["id"],
                    "appliance": as_input(washer, quantity=2),
                }
            ],
        ),
    )
    sample.delete(f"/api/appliances/{washer['id']}")

    response = sample.post(f"/api/simulations/{created['id']}/run")

    assert response.status_code == 422
    assert "changes.0.appliance_id" in response.json()["error"]["fields"]
    assert sample.get(f"/api/simulations/{created['id']}").json()["change_descriptions"] == [
        "Change appliance #" + str(washer["id"]) + " (no longer exists): settings replaced"
    ]
