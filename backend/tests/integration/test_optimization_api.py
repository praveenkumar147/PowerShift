"""Smart Scheduler end to end: API -> solver -> independent validation -> database.

Most tests use the sample household: 6 fixed appliances, 3 flexible ones
(washing machine, dishwasher, water heater), a time-of-use tariff and a 5 kW limit.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from powershift.db.models import OptimizationRunItem
from tests.factories import HOUSEHOLD_PAYLOAD, fixed_payload, flexible_payload
from tests.integration.test_tariffs_api import FLAT

RUN = "/api/optimization/run"


@pytest.fixture
def sample(client: TestClient) -> TestClient:
    assert client.post("/api/demo").status_code == 201
    return client


def run(client: TestClient, **body: Any) -> dict[str, Any]:
    response = client.post(RUN, json=body)
    assert response.status_code == 201, response.json()
    result: dict[str, Any] = response.json()
    return result


def test_cost_goal_finds_a_valid_cheaper_schedule(sample: TestClient) -> None:
    body = run(sample, priority="cost")

    assert body["status"] == "OPTIMAL" and body["proven_optimal"] is True
    assert body["schedule_valid"] is True
    assert [c["code"] for c in body["validation"] if not c["passed"]] == []
    assert len(body["validation"]) == 7
    assert body["optimized"]["monthly_bill"] < body["baseline"]["monthly_bill"]
    assert body["monthly_savings"] == pytest.approx(
        body["baseline"]["monthly_bill"] - body["optimized"]["monthly_bill"], abs=0.005
    )
    assert body["optimized"]["minutes_over_limit"] == 0
    assert {item["name"] for item in body["items"]} == {
        "Washing machine",
        "Dishwasher",
        "Water heater",
    }
    assert all(item["reasons"] for item in body["items"])
    moved = [item for item in body["items"] if item["moved"]]
    assert any(r["code"] == "cheaper_time" for item in moved for r in item["reasons"])
    assert [s["name"] for s in body["stages"]] == ["cost", "peak", "preferred_window", "movement"]
    assert len(body["profile"]["before"]) == len(body["profile"]["after"]) == 96
    assert body["solver"].startswith("OR-Tools CP-SAT")
    assert body["solve_time_ms"] >= 0


def test_peak_goal_never_raises_the_peak(sample: TestClient) -> None:
    body = run(sample, priority="peak")
    assert body["schedule_valid"] is True
    assert body["optimized"]["peak_kw"] <= body["baseline"]["peak_kw"]
    assert body["peak_reduction_kw"] >= 0


def test_goals_trade_cost_against_peak(sample: TestClient) -> None:
    cost, peak = run(sample, priority="cost"), run(sample, priority="peak")
    balanced = run(sample, priority="balanced", balance_weight=50)
    assert (
        cost["optimized"]["weekly_energy_charge"] <= balanced["optimized"]["weekly_energy_charge"]
    )
    assert (
        balanced["optimized"]["weekly_energy_charge"] <= peak["optimized"]["weekly_energy_charge"]
    )
    assert (
        peak["optimized"]["peak_kw"]
        <= balanced["optimized"]["peak_kw"]
        <= cost["optimized"]["peak_kw"]
    )


def test_runs_are_stored_and_reproducible(sample: TestClient) -> None:
    first = run(sample, priority="balanced")
    second = run(sample, priority="balanced")

    assert sample.get(f"/api/optimization/{first['id']}").json() == first
    assert [(i["appliance_id"], i["start_minute"]) for i in first["items"]] == [
        (i["appliance_id"], i["start_minute"]) for i in second["items"]
    ]
    history = sample.get("/api/optimization/history").json()
    assert [h["id"] for h in history] == [second["id"], first["id"]]
    assert history[0]["status"] == "OPTIMAL" and history[0]["schedule_valid"] is True
    assert history[0]["optimized_bill"] == first["optimized"]["monthly_bill"]


def test_optimizing_does_not_change_the_household(sample: TestClient) -> None:
    before = sample.get("/api/appliances").json()
    run(sample, priority="cost")
    assert sample.get("/api/appliances").json() == before


def test_infeasible_household_is_explained_and_stored(sample: TestClient) -> None:
    household = sample.get("/api/household").json()
    sample.put(
        "/api/household", json={**household, "max_load_kw": 2.5}
    )  # 3 kW water heater can't fit

    body = run(sample, priority="cost")

    assert body["status"] == "INFEASIBLE"
    assert body["schedule_valid"] is False and body["items"] == [] and body["optimized"] is None
    assert body["monthly_savings"] is None and body["profile"] is None
    codes = {d["code"] for d in body["diagnostics"]}
    assert "appliance_cannot_fit" in codes and "limit_too_low" in codes
    assert any("Water heater" in d["message"] for d in body["diagnostics"])
    assert sample.get("/api/optimization/history").json()[0]["status"] == "INFEASIBLE"


def test_flat_tariff_gives_zero_savings_and_says_why(sample: TestClient) -> None:
    flat = sample.post("/api/tariffs", json=FLAT).json()
    sample.post(f"/api/tariffs/{flat['id']}/activate")

    body = run(sample, priority="balanced")

    assert body["schedule_valid"] is True
    assert body["monthly_savings"] == 0
    assert any("not time-of-use" in note for note in body["notes"])


def test_unsolvable_inputs_are_rejected_with_a_reason(client: TestClient) -> None:
    client.post("/api/appliances", json=fixed_payload())
    response = client.post(RUN, json={"priority": "peak"})
    assert response.status_code == 422
    assert "no flexible appliances" in response.json()["error"]["fields"]["appliances"]

    client.post("/api/appliances", json=flexible_payload())
    response = client.post(RUN, json={"priority": "cost"})
    assert response.status_code == 422
    assert "without an active tariff" in response.json()["error"]["fields"]["priority"]
    assert client.get("/api/optimization/history").json() == []  # nothing stored


def test_peak_goal_works_without_tariff_or_household(client: TestClient) -> None:
    client.post("/api/appliances", json=flexible_payload())
    body = run(client, priority="peak")
    assert body["schedule_valid"] is True
    assert body["baseline"]["monthly_bill"] is None and body["monthly_savings"] is None
    assert body["load_limit_kw"] is None


def test_request_validation(client: TestClient) -> None:
    assert client.post(RUN, json={"start_step_minutes": 20}).status_code == 422
    assert client.post(RUN, json={"balance_weight": 101}).status_code == 422
    assert client.post(RUN, json={"time_limit_seconds": 0}).status_code == 422
    assert client.post(RUN, json={"priority": "magic"}).status_code == 422
    assert client.get("/api/optimization/999").status_code == 404


def test_finer_start_grid_is_at_least_as_good(sample: TestClient) -> None:
    hourly = run(sample, priority="cost", start_step_minutes=60)
    quarter = run(sample, priority="cost", start_step_minutes=15)
    assert quarter["schedule_valid"] is True
    assert (
        quarter["optimized"]["weekly_energy_charge"] <= hourly["optimized"]["weekly_energy_charge"]
    )


def test_history_survives_deleting_an_appliance(client: TestClient) -> None:
    client.put("/api/household", json=HOUSEHOLD_PAYLOAD)
    appliance = client.post("/api/appliances", json=flexible_payload()).json()
    body = run(client, priority="peak")

    assert client.delete(f"/api/appliances/{appliance['id']}").status_code == 204

    assert (
        client.get(f"/api/optimization/{body['id']}").json()["items"][0]["name"]
        == "Washing machine"
    )
    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        item = session.scalars(select(OptimizationRunItem)).one()
        assert item.appliance_id is None and item.appliance_name == "Washing machine"
