from __future__ import annotations

from fastapi.testclient import TestClient

from tests.factories import HOUSEHOLD_PAYLOAD


def test_household_is_null_before_setup(client: TestClient) -> None:
    response = client.get("/api/household")

    assert response.status_code == 200
    assert response.json() is None


def test_save_then_read_household(client: TestClient) -> None:
    saved = client.put("/api/household", json=HOUSEHOLD_PAYLOAD)

    assert saved.status_code == 200
    assert client.get("/api/household").json() == HOUSEHOLD_PAYLOAD


def test_second_save_updates_the_same_household(client: TestClient) -> None:
    client.put("/api/household", json=HOUSEHOLD_PAYLOAD)

    client.put("/api/household", json={**HOUSEHOLD_PAYLOAD, "occupants": 2})

    assert client.get("/api/household").json()["occupants"] == 2


def test_input_is_normalised(client: TestClient) -> None:
    payload = {
        **HOUSEHOLD_PAYLOAD,
        "name": "  Home  ",
        "currency_code": "usd",
        "location_label": " ",
    }

    body = client.put("/api/household", json=payload).json()

    assert body["name"] == "Home"
    assert body["currency_code"] == "USD"
    assert body["location_label"] is None


def test_invalid_household_reports_each_field(client: TestClient) -> None:
    payload = {**HOUSEHOLD_PAYLOAD, "occupants": 0, "max_load_kw": -1, "currency_code": "RUPEES"}

    response = client.put("/api/household", json=payload)

    assert response.status_code == 422
    assert set(response.json()["error"]["fields"]) == {"occupants", "max_load_kw", "currency_code"}
