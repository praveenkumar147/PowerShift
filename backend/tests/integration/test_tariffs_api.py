from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

FLAT: dict[str, Any] = {
    "name": "Flat",
    "tariff_type": "flat",
    "effective_date": "2026-04-01",
    "flat_rate_per_kwh": 6.5,
    "charges": [
        {"kind": "fixed_monthly", "label": "Meter rent", "amount": 50},
        {"kind": "percentage", "label": "Duty", "amount": 5},
    ],
}

TOU: dict[str, Any] = {
    "name": "Time of use",
    "tariff_type": "tou",
    "effective_date": "2026-04-01",
    "tou_periods": [
        {"day_type": "all", "start_minute": 1320, "end_minute": 360, "rate_per_kwh": 3},
        {"day_type": "all", "start_minute": 360, "end_minute": 1320, "rate_per_kwh": 7.25},
    ],
}

SLAB: dict[str, Any] = {
    "name": "Slabs",
    "tariff_type": "slab",
    "effective_date": "2026-04-01",
    "slab_mode": "telescopic",
    "slabs": [
        {"up_to_kwh": 100, "rate_per_kwh": 3},
        {"up_to_kwh": None, "rate_per_kwh": 5},
    ],
}


def create(client: TestClient, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/tariffs", json=body)
    assert response.status_code == 201, response.json()
    result: dict[str, Any] = response.json()
    return result


def test_first_tariff_becomes_active_and_round_trips(client: TestClient) -> None:
    body = create(client, FLAT)

    assert body["is_active"] is True
    assert body["flat_rate_per_kwh"] == 6.5
    assert body["charges"][0] == {"kind": "fixed_monthly", "label": "Meter rent", "amount": 50.0}
    assert client.get(f"/api/tariffs/{body['id']}").json() == body


def test_later_tariffs_are_inactive_until_activated(client: TestClient) -> None:
    flat = create(client, FLAT)
    tou = create(client, TOU)
    assert tou["is_active"] is False

    activated = client.post(f"/api/tariffs/{tou['id']}/activate").json()

    assert activated["is_active"] is True
    listed = client.get("/api/tariffs").json()
    assert [(t["id"], t["is_active"]) for t in listed] == [(tou["id"], True), (flat["id"], False)]


def test_decimal_rates_are_stored_exactly(client: TestClient) -> None:
    body = create(client, {**FLAT, "flat_rate_per_kwh": 0.1234})
    assert body["flat_rate_per_kwh"] == 0.1234


def test_update_replaces_child_rows(client: TestClient) -> None:
    created = create(client, FLAT)

    updated = client.put(f"/api/tariffs/{created['id']}", json={**FLAT, "charges": []}).json()

    assert updated["charges"] == []
    assert updated["is_active"] is True  # editing does not change which tariff is active


def test_deleting_the_active_tariff_leaves_none_active(client: TestClient) -> None:
    flat = create(client, FLAT)
    create(client, TOU)

    assert client.delete(f"/api/tariffs/{flat['id']}").status_code == 204
    assert not any(t["is_active"] for t in client.get("/api/tariffs").json())


def test_missing_tariff_is_404(client: TestClient) -> None:
    assert client.get("/api/tariffs/9").status_code == 404
    assert client.post("/api/tariffs/9/activate").status_code == 404
    assert client.delete("/api/tariffs/9").status_code == 404


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({**FLAT, "flat_rate_per_kwh": None}, "flat_rate_per_kwh"),
        ({**FLAT, "flat_rate_per_kwh": -1}, "flat_rate_per_kwh"),
        ({**TOU, "tou_periods": TOU["tou_periods"][:1]}, "tou_periods"),
        (
            {
                **SLAB,
                "slabs": [
                    {"up_to_kwh": None, "rate_per_kwh": 3},
                    {"up_to_kwh": 50, "rate_per_kwh": 4},
                ],
            },
            "slabs.0.up_to_kwh",
        ),
        ({**FLAT, "charges": [{"kind": "percentage", "label": "Tax", "amount": 150}]}, "charges.0"),
        (
            {**FLAT, "charges": [{"kind": "fixed_monthly", "label": " ", "amount": 1}]},
            "charges.0.label",
        ),
        ({**FLAT, "tariff_type": "dynamic"}, "tariff_type"),
        ({**FLAT, "effective_date": "yesterday"}, "effective_date"),
    ],
)
def test_invalid_tariffs_are_rejected_with_field_paths(
    client: TestClient, body: dict[str, Any], field: str
) -> None:
    response = client.post("/api/tariffs", json=body)

    assert response.status_code == 422
    assert field in response.json()["error"]["fields"]
    assert client.get("/api/tariffs").json() == []


def test_tou_gap_message_names_the_time(client: TestClient) -> None:
    response = client.post("/api/tariffs", json={**TOU, "tou_periods": TOU["tou_periods"][1:]})
    assert response.json()["error"]["fields"]["tou_periods"] == "No price is set for 00:00."
