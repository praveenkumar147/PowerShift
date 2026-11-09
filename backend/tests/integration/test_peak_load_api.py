from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.factories import HOUSEHOLD_PAYLOAD, fixed_payload, flexible_payload


def washer(**changes: Any) -> dict[str, Any]:
    payload = flexible_payload(**changes)
    payload["flexible"]["current_start_minute"] = 1140  # 19:00-20:30, Mon/Thu/Sat
    return payload


@pytest.fixture
def home(client: TestClient) -> TestClient:
    client.put("/api/household", json={**HOUSEHOLD_PAYLOAD, "max_load_kw": 2.0})
    client.post("/api/appliances", json=fixed_payload())  # fridge 0.15 kW all day
    client.post("/api/appliances", json=washer())  # 2 kW
    return client


def test_analysis_picks_the_worst_day_and_reports_violation(home: TestClient) -> None:
    body = home.get("/api/peak-load/analysis").json()

    assert body["weekday"] == 0 and body["selected_automatically"] is True
    assert body["load_limit_kw"] == 2.0
    assert body["peak_kw"] == 2.15
    assert body["peak_expected_kw"] == 1.06
    assert body["headroom_kw"] == -0.15
    assert body["minutes_over_limit"] == 90
    assert body["peak_windows"] == [{"start_minute": 1140, "end_minute": 1230, "minutes": 90}]
    assert [c["name"] for c in body["peak_contributors"]] == ["Washing machine", "Refrigerator"]
    assert body["peak_fixed_kw"] == 0.15 and body["peak_flexible_kw"] == 2.0
    (violation,) = body["violations"]
    assert violation["max_kw"] == 2.15
    assert [a["name"] for a in violation["appliances"]] == ["Washing machine", "Refrigerator"]
    assert len(body["steps"]) == 96
    assert [d["minutes_over_limit"] for d in body["week"]] == [90, 0, 0, 90, 0, 90, 0]


def test_requested_weekday_is_respected(home: TestClient) -> None:
    body = home.get("/api/peak-load/analysis?weekday=1").json()

    assert body["weekday"] == 1 and body["selected_automatically"] is False
    assert body["peak_kw"] == 0.15
    assert body["violations"] == []
    assert body["headroom_kw"] == 1.85


def test_steps_list_running_appliances(home: TestClient) -> None:
    steps = home.get("/api/peak-load/analysis?weekday=0").json()["steps"]
    at_19 = steps[19 * 4]
    assert at_19["start_minute"] == 1140
    assert len(at_19["appliance_ids"]) == 2
    assert steps[0]["appliance_ids"] == [steps[0]["appliance_ids"][0]]  # fridge only


def test_conflicts_between_not_simultaneous_appliances(home: TestClient) -> None:
    dishwasher = washer(name="Dishwasher", operating_days=[0])
    dishwasher["flexible"]["current_start_minute"] = 1200  # 20:00, overlaps washer until 20:30
    home.post("/api/appliances", json=dishwasher)

    body = home.get("/api/peak-load/analysis?weekday=0").json()

    (conflict,) = body["conflicts"]
    assert (conflict["start_minute"], conflict["end_minute"]) == (1200, 1230)
    assert {a["name"] for a in conflict["appliances"]} == {"Washing machine", "Dishwasher"}
    assert body["overlaps"][0]["max_kw"] == 4.0


def test_without_household_limit(client: TestClient) -> None:
    client.post("/api/appliances", json=washer())

    body = client.get("/api/peak-load/analysis").json()

    assert body["load_limit_kw"] is None and body["headroom_kw"] is None
    assert body["violations"] == []
    assert any("No household load limit" in note for note in body["notes"])


def test_empty_household(client: TestClient) -> None:
    body = client.get("/api/peak-load/analysis").json()
    assert body["peak_kw"] == 0 and body["peak_windows"] == [] and body["peak_contributors"] == []


def test_invalid_weekday(client: TestClient) -> None:
    assert client.get("/api/peak-load/analysis?weekday=7").status_code == 422
