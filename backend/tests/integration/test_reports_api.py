"""All seven reports, both formats, through the API, checked against the app's own figures."""

from __future__ import annotations

import csv
import io
import re
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.factories import fixed_payload, flexible_payload

KINDS = [
    "daily_energy",
    "monthly_energy",
    "appliance_consumption",
    "bill_estimate",
    "peak_load",
    "optimization_comparison",
    "simulation_comparison",
]
TODAY = date.today()
MONTH = {"year": TODAY.year, "month": TODAY.month}


@pytest.fixture
def full(client: TestClient) -> TestClient:
    """Sample household, one optimization run and one scenario that has been run."""
    assert client.post("/api/demo").status_code == 201
    assert client.post("/api/optimization/run", json={"priority": "cost"}).status_code == 201
    scenario = client.post(
        "/api/simulations",
        json={"name": "Higher limit", "changes": [{"type": "set_load_limit", "max_load_kw": 8}]},
    )
    assert client.post(f"/api/simulations/{scenario.json()['id']}/run").status_code == 201
    return client


def export(client: TestClient, kind: str, fmt: str = "csv", **params: Any) -> Any:
    return client.post("/api/reports/export", json={"type": kind, "format": fmt, "params": params})


def table(response: Any) -> list[list[str]]:
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


def find_row(rows: list[list[str]], first: str, width: int | None = None) -> list[str]:
    """First row starting with `first` (and, optionally, having exactly `width` cells)."""
    return next(r for r in rows if r and r[0] == first and (width is None or len(r) == width))


@pytest.mark.parametrize("fmt", ["csv", "pdf"])
@pytest.mark.parametrize("kind", KINDS)
def test_every_report_exports_in_both_formats(full: TestClient, kind: str, fmt: str) -> None:
    response = export(full, kind, fmt)

    assert response.status_code == 200, response.text
    disposition = response.headers["content-disposition"]
    assert re.fullmatch(
        rf'attachment; filename="powershift-{kind.replace("_", "-")}-\d{{8}}\.{fmt}"', disposition
    )
    if fmt == "pdf":
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF-") and response.content.rstrip().endswith(
            b"%%EOF"
        )
    else:
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        rows = table(response)
        # Every report states what it is, when it was made, that it is an estimate, and its assumptions.
        labels = [r[0] for r in rows if r]
        assert "PowerShift report" in labels and "Generated" in labels
        assert find_row(rows, "Basis")[1].startswith("ESTIMATED")
        assert "Calculation assumptions" in labels
        assert "Household" in labels and find_row(rows, "Currency")[1] == "INR"


def test_daily_report_matches_the_energy_figures(full: TestClient) -> None:
    api = full.get(f"/api/energy/report?start={TODAY:%Y-%m}-01&end={TODAY:%Y-%m}-07").json()
    rows = table(export(full, "daily_energy", start=f"{TODAY:%Y-%m}-01", end=f"{TODAY:%Y-%m}-07"))

    assert ["Date", "Weekday", "Energy (kWh)", "Energy charge (INR)"] in rows
    total = find_row(rows, "Total")
    assert total[1] == "7 days"
    assert float(total[2]) == api["total_kwh"] and float(total[3]) == api["energy_charge"]
    first = find_row(rows, f"{TODAY:%Y-%m}-01")
    assert float(first[2]) == api["daily"][0]["kwh"]
    assert find_row(rows, "Period")[1] == f"{TODAY:%Y-%m}-01 to {TODAY:%Y-%m}-07 (7 days)"


def test_reports_include_the_relevant_tariff_configuration(full: TestClient) -> None:
    rows = table(export(full, "bill_estimate", **MONTH))
    assert ["Tariff configuration"] in rows
    assert find_row(rows, "Price 00:00-06:00 (every day)")[1] == "4.5 per kWh"
    assert find_row(rows, "Fuel adjustment (sample)")[1] == "0.3 per kWh"
    assert find_row(rows, "Electricity duty (sample)")[1] == "5% of subtotal"
    assert find_row(rows, "Type")[1] == "Time of use"


def test_bill_report_matches_the_bill_endpoint_line_by_line(full: TestClient) -> None:
    bill = full.get(f"/api/energy/bill?year={TODAY.year}&month={TODAY.month}").json()
    rows = table(export(full, "bill_estimate", **MONTH))

    assert ["Item", "Basis", "Amount (INR)"] in rows
    for line in bill["lines"]:
        assert float(find_row(rows, line["label"], width=3)[2]) == line["amount"]
    assert float(find_row(rows, "Estimated total")[2]) == bill["total"]
    assert float(find_row(rows, "Energy (kWh)")[1]) == bill["total_kwh"]


def test_monthly_report_totals(full: TestClient) -> None:
    api = full.get(f"/api/energy/monthly?year={TODAY.year}").json()["months"]
    rows = table(export(full, "monthly_energy", year=TODAY.year))

    assert len([r for r in rows if r and r[0] in ("January", "June", "December")]) == 3
    total = find_row(rows, "Total")
    assert float(total[2]) == pytest.approx(sum(m["kwh"] for m in api), abs=0.01)
    assert float(total[3]) == pytest.approx(sum(m["bill_total"] for m in api), abs=0.01)


def test_appliance_report_lists_every_appliance_and_category(full: TestClient) -> None:
    rows = table(
        export(full, "appliance_consumption", start=f"{TODAY:%Y-%m}-01", end=f"{TODAY:%Y-%m}-28")
    )
    names = {r[0] for r in rows if len(r) > 3 and r[2] in ("fixed", "flexible")}
    assert names == {a["name"] for a in full.get("/api/appliances").json()}
    assert ["Category", "Energy (kWh)", "Share of energy (%)", "Energy charge (INR)"] in rows


def test_peak_report_distinguishes_power_from_energy(full: TestClient) -> None:
    api = full.get("/api/peak-load/analysis").json()
    rows = table(export(full, "peak_load"))

    assert ["Summary (power in kW, not energy in kWh)"] in rows
    assert float(find_row(rows, "Peak demand, worst case (kW)")[1]) == api["peak_kw"]
    assert float(find_row(rows, "Household load limit (kW)")[1]) == api["load_limit_kw"]
    assert len([r for r in rows if r and re.fullmatch(r"\d\d:00-\d\d:00", r[0])]) == 24
    assert ["Highest demand in each hour"] in rows


def test_optimization_report_has_schedule_validation_and_savings(full: TestClient) -> None:
    run = full.get("/api/optimization/history").json()[0]
    detail = full.get(f"/api/optimization/{run['id']}").json()
    rows = table(export(full, "optimization_comparison", run_id=run["id"]))

    assert find_row(rows, "Status")[1] == "OPTIMAL"
    assert find_row(rows, "Estimated monthly savings (negative = costs more)")[2] == str(
        detail["monthly_savings"]
    )
    assert {i["name"] for i in detail["items"]} <= {r[0] for r in rows if r}
    assert any(
        r and r[0] == "Each run is inside its allowed window" and r[1] == "Pass" for r in rows
    )
    assert ["Independent validation"] in rows


def test_optimization_report_defaults_to_the_latest_run(full: TestClient) -> None:
    full.post("/api/optimization/run", json={"priority": "peak"})
    rows = table(export(full, "optimization_comparison"))
    assert find_row(rows, "Goal")[1] == "peak"


def test_simulation_report_compares_scenarios_with_the_current_household(full: TestClient) -> None:
    rows = table(export(full, "simulation_comparison"))

    assert find_row(rows, "Measure") == ["Measure", "Current household", "Higher limit"]
    assert ["Scenario", "Changes"] in rows
    assert find_row(rows, "Higher limit") == ["Higher limit", "Load limit 5 kW → 8 kW"]
    assert find_row(rows, "Scheduling result")[2] == "OPTIMAL"


def test_scenario_filter(full: TestClient) -> None:
    other = full.post("/api/simulations", json={"name": "Second", "changes": []}).json()
    full.post(f"/api/simulations/{other['id']}/run")
    only = table(export(full, "simulation_comparison", scenario_ids=[other["id"]]))
    assert find_row(only, "Measure")[2:] == ["Second"]


def test_user_typed_names_cannot_inject_spreadsheet_formulas(client: TestClient) -> None:
    client.post("/api/appliances", json=fixed_payload(name="=cmd|' /C calc'!A0"))
    client.post("/api/appliances", json=flexible_payload(name="+SUM(1+1)"))
    rows = table(
        export(client, "appliance_consumption", start=f"{TODAY:%Y-%m}-01", end=f"{TODAY:%Y-%m}-28")
    )
    assert any(r and r[0] == "'=cmd|' /C calc'!A0" for r in rows)
    assert any(r and r[0] == "'+SUM(1+1)" for r in rows)
    assert not any(r and r[0].startswith(("=", "+")) for r in rows)


def test_reports_without_a_tariff_or_household_say_so_and_do_not_invent_costs(
    client: TestClient,
) -> None:
    client.post("/api/appliances", json=fixed_payload())
    rows = table(export(client, "bill_estimate", **MONTH))
    assert not any(r and r[0] == "Estimated total" for r in rows)
    assert not any(r and r[0] == "Currency" for r in rows)
    assert any("No active tariff" in cell for r in rows for cell in r)
    assert ["Tariff configuration"] not in rows

    daily = table(export(client, "daily_energy"))
    assert ["Date", "Weekday", "Energy (kWh)"] in daily  # no cost column without a tariff


def test_reports_do_not_modify_anything(full: TestClient) -> None:
    before = (
        full.get("/api/appliances").json(),
        full.get("/api/tariffs").json(),
        full.get("/api/household").json(),
        full.get("/api/optimization/history").json(),
        full.get("/api/simulations").json(),
    )
    for kind in KINDS:
        export(full, kind, "pdf")
    after = (
        full.get("/api/appliances").json(),
        full.get("/api/tariffs").json(),
        full.get("/api/household").json(),
        full.get("/api/optimization/history").json(),
        full.get("/api/simulations").json(),
    )
    assert before == after


# --- Errors -----------------------------------------------------------------------------------


def test_reports_that_need_data_explain_what_is_missing(sample_less: TestClient) -> None:
    response = export(sample_less, "optimization_comparison")
    assert response.status_code == 422
    assert response.json()["error"]["fields"]["run_id"] == "Run the Smart Scheduler first."

    response = export(sample_less, "simulation_comparison")
    assert response.status_code == 422 and "scenario_ids" in response.json()["error"]["fields"]


@pytest.fixture
def sample_less(client: TestClient) -> TestClient:
    return client


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"type": "nope", "format": "csv"}, 422),
        ({"type": "daily_energy", "format": "xlsx"}, 422),
        ({"type": "daily_energy"}, 422),
        ({"type": "daily_energy", "format": "csv", "params": {"month": 13}}, 422),
        ({"type": "daily_energy", "format": "csv", "params": {"weekday": 9}}, 422),
        ({"type": "daily_energy", "format": "csv", "params": {"start": "yesterday"}}, 422),
        ({"type": "daily_energy", "format": "csv", "params": {"surprise": 1}}, 422),
        (
            {
                "type": "daily_energy",
                "format": "csv",
                "params": {"start": "2026-11-30", "end": "2026-11-01"},
            },
            422,
        ),
        (
            {
                "type": "daily_energy",
                "format": "csv",
                "params": {"start": "2020-01-01", "end": "2026-01-01"},
            },
            422,
        ),
        ({"type": "optimization_comparison", "format": "csv", "params": {"run_id": 999}}, 404),
    ],
)
def test_invalid_requests_are_rejected_without_leaking_internals(
    client: TestClient, body: dict[str, Any], status: int
) -> None:
    response = client.post("/api/reports/export", json=body)
    assert response.status_code == status
    assert "Traceback" not in response.text and set(response.json()) == {"error"}
