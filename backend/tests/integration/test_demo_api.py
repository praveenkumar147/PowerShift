from __future__ import annotations

from fastapi.testclient import TestClient

from powershift.services.demo_service import SAMPLE_APPLIANCES, SAMPLE_HOUSEHOLD, SAMPLE_TARIFF
from tests.factories import HOUSEHOLD_PAYLOAD


def test_sample_data_loads_into_empty_database_and_is_labelled(client: TestClient) -> None:
    response = client.post("/api/demo")

    assert response.status_code == 201
    assert client.get("/api/household").json()["name"] == SAMPLE_HOUSEHOLD
    tariffs = client.get("/api/tariffs").json()
    assert [(t["name"], t["is_active"]) for t in tariffs] == [(SAMPLE_TARIFF, True)]
    assert "not a real utility tariff" in SAMPLE_TARIFF
    assert len(client.get("/api/appliances").json()) == len(SAMPLE_APPLIANCES)


def test_sample_data_produces_a_bill(client: TestClient) -> None:
    client.post("/api/demo")
    bill = client.get("/api/energy/bill?year=2026&month=11").json()
    assert bill["total"] > 0
    assert len(bill["lines"]) == 4  # energy, fixed, per-kWh, duty


def test_sample_data_refuses_to_mix_with_real_data(client: TestClient) -> None:
    client.put("/api/household", json=HOUSEHOLD_PAYLOAD)

    response = client.post("/api/demo")

    assert response.status_code == 409
    assert client.get("/api/appliances").json() == []


def test_sample_data_cannot_be_loaded_twice(client: TestClient) -> None:
    client.post("/api/demo")
    assert client.post("/api/demo").status_code == 409
