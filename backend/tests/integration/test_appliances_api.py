from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from powershift.db.models import ApplianceFlexConstraint, ApplianceOperatingDay
from tests.factories import HOUSEHOLD_PAYLOAD, fixed_payload, flexible_payload


def create(client: TestClient, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/appliances", json=payload)
    assert response.status_code == 201, response.json()
    body: dict[str, Any] = response.json()
    return body


def count_rows(client: TestClient, model: type) -> int:
    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        return int(session.scalar(select(func.count()).select_from(model)))


# --- Create and read ------------------------------------------------------------


def test_create_fixed_appliance_returns_it_with_estimates(client: TestClient) -> None:
    body = create(client, fixed_payload())

    assert body["id"] > 0
    assert body["name"] == "Refrigerator"
    assert body["fixed_blocks"] == [{"start_minute": 0, "end_minute": 1440}]
    assert body["estimates"]["average_power_kw"] == pytest.approx(0.06)
    assert body["estimates"]["energy_per_operating_day_kwh"] == pytest.approx(1.44)
    assert body["warnings"] == []


def test_create_flexible_appliance_round_trips_all_settings(client: TestClient) -> None:
    payload = flexible_payload()
    payload["flexible"]["preferred_start_minute"] = 600
    payload["flexible"]["preferred_end_minute"] = 900

    body = create(client, payload)
    fetched = client.get(f"/api/appliances/{body['id']}").json()

    assert fetched["flexible"] == payload["flexible"]
    assert fetched["operating_days"] == [0, 3, 5]
    assert fetched["estimates"]["energy_per_week_kwh"] == pytest.approx(4.5)


def test_operating_days_are_sorted(client: TestClient) -> None:
    body = create(client, fixed_payload(operating_days=[6, 0, 3]))
    assert body["operating_days"] == [0, 3, 6]


def test_get_missing_appliance_is_404(client: TestClient) -> None:
    response = client.get("/api/appliances/999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- List, search and filter ------------------------------------------------------


def test_list_is_sorted_by_name_and_filterable(client: TestClient) -> None:
    create(client, fixed_payload(name="router", category="electronics"))
    create(client, flexible_payload(name="Dishwasher", category="kitchen"))
    create(client, fixed_payload(name="Ceiling lights", category="lighting"))

    def names(query: str = "") -> list[str]:
        return [a["name"] for a in client.get(f"/api/appliances{query}").json()]

    assert names() == ["Ceiling lights", "Dishwasher", "router"]
    assert names("?category=kitchen") == ["Dishwasher"]
    assert names("?mode=fixed") == ["Ceiling lights", "router"]
    assert names("?q=LIGHT") == ["Ceiling lights"]
    assert names("?q=light&mode=flexible") == []


def test_search_treats_wildcards_literally(client: TestClient) -> None:
    create(client, fixed_payload(name="Fan"))
    assert client.get("/api/appliances?q=%25").json() == []  # "%" must not match everything


def test_invalid_filter_value_is_422(client: TestClient) -> None:
    assert client.get("/api/appliances?category=spaceship").status_code == 422


# --- Update -----------------------------------------------------------------------


def test_update_changes_fields_and_replaces_children(client: TestClient) -> None:
    created = create(client, flexible_payload())
    changed = flexible_payload(name="Washer", operating_days=[0, 1])
    changed["flexible"]["run_duration_minutes"] = 60

    response = client.put(f"/api/appliances/{created['id']}", json=changed)

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Washer"
    assert body["operating_days"] == [0, 1]
    assert body["flexible"]["run_duration_minutes"] == 60
    assert count_rows(client, ApplianceOperatingDay) == 2
    assert count_rows(client, ApplianceFlexConstraint) == 1


def test_switching_flexible_to_fixed_removes_flexible_settings(client: TestClient) -> None:
    created = create(client, flexible_payload())

    body = client.put(
        f"/api/appliances/{created['id']}", json=fixed_payload(name="Washing machine")
    ).json()

    assert body["mode"] == "fixed"
    assert body["flexible"] is None
    assert count_rows(client, ApplianceFlexConstraint) == 0


def test_update_missing_appliance_is_404(client: TestClient) -> None:
    assert client.put("/api/appliances/999", json=fixed_payload()).status_code == 404


def test_update_may_keep_its_own_name(client: TestClient) -> None:
    created = create(client, fixed_payload())
    response = client.put(f"/api/appliances/{created['id']}", json=fixed_payload(quantity=2))
    assert response.status_code == 200


# --- Delete -----------------------------------------------------------------------


def test_delete_removes_appliance_and_its_child_rows(client: TestClient) -> None:
    created = create(client, flexible_payload())

    response = client.delete(f"/api/appliances/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/appliances/{created['id']}").status_code == 404
    assert count_rows(client, ApplianceOperatingDay) == 0
    assert count_rows(client, ApplianceFlexConstraint) == 0


def test_delete_missing_appliance_is_404(client: TestClient) -> None:
    assert client.delete("/api/appliances/999").status_code == 404


# --- Validation ---------------------------------------------------------------------


def test_duplicate_name_is_conflict_regardless_of_case(client: TestClient) -> None:
    create(client, fixed_payload(name="Fridge"))

    response = client.post("/api/appliances", json=fixed_payload(name="FRIDGE"))

    assert response.status_code == 409
    assert "name" in response.json()["error"]["fields"]


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"name": "   "}, "name"),
        ({"rated_power_w": 0}, "rated_power_w"),
        ({"rated_power_w": 250_000}, "rated_power_w"),
        ({"quantity": 0}, "quantity"),
        ({"duty_cycle": 0}, "duty_cycle"),
        ({"duty_cycle": 1.5}, "duty_cycle"),
        ({"category": "toaster"}, "category"),
        ({"operating_days": []}, "operating_days"),
        ({"operating_days": [1, 1]}, "operating_days"),
        ({"operating_days": [7]}, "operating_days.0"),
        ({"fixed_blocks": [{"start_minute": 10, "end_minute": 60}]}, "fixed_blocks.0.start_minute"),
        ({"fixed_blocks": [{"start_minute": 0, "end_minute": 1500}]}, "fixed_blocks.0.end_minute"),
        ({"unexpected": 1}, "unexpected"),
    ],
)
def test_field_validation_names_the_field(
    client: TestClient, changes: dict[str, Any], field: str
) -> None:
    response = client.post("/api/appliances", json=fixed_payload(**changes))

    assert response.status_code == 422
    assert field in response.json()["error"]["fields"]


def test_cross_field_rule_reports_field_path(client: TestClient) -> None:
    payload = flexible_payload()
    payload["flexible"]["latest_end_minute"] = 540  # 08:00-09:00 window, 90-minute run

    response = client.post("/api/appliances", json=payload)

    assert response.status_code == 422
    fields = response.json()["error"]["fields"]
    assert "cannot fit" in fields["flexible.run_duration_minutes"]


def test_preferred_window_needs_both_ends(client: TestClient) -> None:
    payload = flexible_payload()
    payload["flexible"]["preferred_start_minute"] = 600

    response = client.post("/api/appliances", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["flexible"] == (
        "Set both preferred start and end, or leave both empty."
    )


def test_invalid_appliance_is_not_saved(client: TestClient) -> None:
    client.post("/api/appliances", json=fixed_payload(fixed_blocks=[]))
    assert client.get("/api/appliances").json() == []


# --- Warnings -----------------------------------------------------------------------


def test_warns_when_one_appliance_exceeds_household_limit(client: TestClient) -> None:
    client.put("/api/household", json={**HOUSEHOLD_PAYLOAD, "max_load_kw": 3})

    body = create(client, flexible_payload(rated_power_w=2000, quantity=2))

    assert len(body["warnings"]) == 1
    assert "4.00 kW" in body["warnings"][0]
    assert "3.00 kW" in body["warnings"][0]
