"""Energy endpoints over the real database. Arithmetic is covered in unit tests;
these check wiring, rounding, filters, notes and error handling."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.factories import fixed_payload, flexible_payload
from tests.integration.test_tariffs_api import FLAT, SLAB, create

NOV = "start=2026-11-01&end=2026-11-30"


@pytest.fixture
def household(client: TestClient) -> TestClient:
    client.post("/api/appliances", json=fixed_payload())  # 1.44 kWh/day
    flex = flexible_payload()
    flex["flexible"]["current_start_minute"] = 1140  # 19:00
    client.post("/api/appliances", json=flex)  # 1.5 kWh on Mon, Thu, Sat
    return client


def test_report_without_tariff_has_energy_but_no_costs(household: TestClient) -> None:
    body = household.get(f"/api/energy/report?{NOV}").json()

    assert body["days"] == 30
    assert body["total_kwh"] == 62.7
    assert body["average_daily_kwh"] == 2.09
    assert body["energy_charge"] is None
    assert body["tariff"] is None
    assert "No active tariff, so costs are not calculated." in body["notes"]
    assert [a["name"] for a in body["appliances"]] == ["Refrigerator", "Washing machine"]
    assert body["appliances"][0]["share"] == pytest.approx(43.2 / 62.7, abs=1e-4)


def test_report_with_flat_tariff(household: TestClient) -> None:
    create(household, FLAT)  # 6.5 per kWh

    body = household.get(f"/api/energy/report?{NOV}").json()

    assert body["energy_charge"] == pytest.approx(62.7 * 6.5)
    assert body["daily"][0] == {"date": "2026-11-01", "kwh": 1.44, "energy_charge": 9.36}
    assert {c["category"] for c in body["categories"]} == {"kitchen", "laundry"}
    assert body["tariff"]["name"] == "Flat"


def test_report_category_filter(household: TestClient) -> None:
    body = household.get(f"/api/energy/report?{NOV}&category=laundry").json()
    assert body["total_kwh"] == 19.5
    assert [a["name"] for a in body["appliances"]] == ["Washing machine"]


def test_report_rejects_reversed_or_huge_ranges(household: TestClient) -> None:
    reversed_range = household.get("/api/energy/report?start=2026-11-30&end=2026-11-01")
    assert reversed_range.status_code == 422
    assert "end" in reversed_range.json()["error"]["fields"]

    assert household.get("/api/energy/report?start=2026-01-01&end=2027-06-01").status_code == 422
    assert household.get("/api/energy/report?start=nope&end=2026-01-01").status_code == 422


def test_hourly_profile(household: TestClient) -> None:
    body = household.get("/api/energy/hourly-profile?weekday=0").json()

    assert len(body["hours"]) == 24
    assert body["hours"][19]["flexible_kwh"] == 1.0
    assert body["hours"][19]["fixed_kwh"] == 0.06
    assert household.get("/api/energy/hourly-profile?weekday=7").status_code == 422


def test_monthly_projection_and_bill(household: TestClient) -> None:
    create(household, FLAT)  # 6.5/kWh, 50 fixed, 5% duty

    months = household.get("/api/energy/monthly?year=2026").json()["months"]
    bill = household.get("/api/energy/bill?year=2026&month=11").json()

    # 62.7 x 6.5 = 407.55; + 50 = 457.55; duty 5% = 22.8775 -> 22.88; total 480.43
    assert [line["amount"] for line in bill["lines"]] == [407.55, 50.0, 22.88]
    assert bill["total"] == 480.43
    assert bill["effective_rate_per_kwh"] == pytest.approx(480.43 / 62.7, abs=1e-4)
    assert months[10]["bill_total"] == bill["total"]


def test_slab_report_notes_the_allocation_rule(household: TestClient) -> None:
    create(household, SLAB)
    notes = household.get(f"/api/energy/report?{NOV}").json()["notes"]
    assert any("average energy rate" in note for note in notes)


def test_bill_without_tariff(household: TestClient) -> None:
    body = household.get("/api/energy/bill?year=2026&month=11").json()
    assert body["total"] is None and body["lines"] == []
    assert body["total_kwh"] == 62.7


def test_empty_household_reports_zero(client: TestClient) -> None:
    body = client.get(f"/api/energy/report?{NOV}").json()
    assert body["total_kwh"] == 0 and body["appliances"] == []
