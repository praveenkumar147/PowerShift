"""Backups, restore, export, reset and 'about', end to end against a real database."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from powershift.core.config import Settings
from powershift.db.migrate import build_alembic_config, head_revision
from tests.factories import HOUSEHOLD_PAYLOAD, fixed_payload
from tests.unit.test_backup_validation import execute, old_database

BINARY = {"Content-Type": "application/octet-stream"}


@pytest.fixture
def settings_of(client: TestClient) -> Settings:
    settings: Settings = client.app.state.settings  # type: ignore[attr-defined]
    return settings


def appliance_names(client: TestClient) -> list[str]:
    return [a["name"] for a in client.get("/api/appliances").json()]


def make_backup(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/settings/backup")
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def error_fields(response: Any) -> dict[str, str]:
    fields: dict[str, str] = response.json()["error"]["fields"]
    return fields


@pytest.fixture
def home(client: TestClient) -> TestClient:
    client.put("/api/household", json=HOUSEHOLD_PAYLOAD)
    client.post("/api/appliances", json=fixed_payload(name="Refrigerator"))
    return client


# --- About, create and list ------------------------------------------------------------------


def test_about_describes_this_installation(home: TestClient, settings_of: Settings) -> None:
    about = home.get("/api/settings/about").json()

    assert about["database_path"] == str(settings_of.database_path)
    assert about["data_dir"] == str(settings_of.data_dir) and about["backups_dir"] == str(
        settings_of.backups_dir
    )
    assert about["schema_revision"] == head_revision(build_alembic_config())
    assert about["solver"].startswith("OR-Tools CP-SAT") and about["app_version"] == "0.1.0"
    assert about["counts"] == {
        "household": 1,
        "appliances": 1,
        "tariffs": 0,
        "simulation_scenarios": 0,
        "optimization_runs": 0,
    }
    assert about["database_size_bytes"] > 0


def test_creating_a_backup_makes_one_valid_file_listed_newest_first(
    home: TestClient, settings_of: Settings
) -> None:
    first, second = make_backup(home), make_backup(home)

    assert (
        first["kind"] == "manual"
        and first["name"].startswith("manual-")
        and first["name"].endswith(".db")
    )
    assert first["name"] != second["name"]  # two in the same second never overwrite each other
    listed = home.get("/api/settings/backups").json()
    assert [b["name"] for b in listed][:2] == [second["name"], first["name"]]
    assert (settings_of.backups_dir / first["name"]).stat().st_size == first["size_bytes"]
    summary = home.get(f"/api/settings/backups/{first['name']}/check").json()
    assert summary["appliances"] == 1 and summary["household_name"] == "Test home"


def test_listing_labels_who_made_each_backup(home: TestClient, settings_of: Settings) -> None:
    for name in (
        "pre-migration-0003-20260101T000000Z.db",
        "pre-restore-20260101T000000Z.db",
        "pre-reset-20260101T000000Z.db",
        "weird.db",
    ):
        (settings_of.backups_dir / name).write_bytes(b"x")
    (settings_of.backups_dir / "notes.txt").write_text("not a backup")
    kinds = {b["name"]: b["kind"] for b in home.get("/api/settings/backups").json()}
    assert kinds == {
        "pre-migration-0003-20260101T000000Z.db": "pre-migration",
        "pre-restore-20260101T000000Z.db": "pre-restore",
        "pre-reset-20260101T000000Z.db": "pre-reset",
        "weird.db": "other",
    }


def test_downloading_a_backup_returns_exactly_the_file(
    home: TestClient, settings_of: Settings
) -> None:
    backup = make_backup(home)
    response = home.get(f"/api/settings/backups/{backup['name']}")
    assert response.status_code == 200
    assert response.content == (settings_of.backups_dir / backup["name"]).read_bytes()
    assert "attachment" in response.headers["content-disposition"]


# --- Restore ------------------------------------------------------------------------------------


def test_restore_brings_back_deleted_data_and_keeps_a_safety_backup(home: TestClient) -> None:
    backup = make_backup(home)
    home.delete(f"/api/appliances/{home.get('/api/appliances').json()[0]['id']}")
    home.post("/api/appliances", json=fixed_payload(name="Added later"))
    assert appliance_names(home) == ["Added later"]

    response = home.post(f"/api/settings/backups/{backup['name']}/restore")

    assert response.status_code == 200, response.text
    result = response.json()
    assert appliance_names(home) == ["Refrigerator"]
    assert result["restored"]["appliances"] == 1
    assert result["safety_backup"]["kind"] == "pre-restore"
    assert result["schema_revision"] == head_revision(build_alembic_config())
    # The restore itself can be undone: the safety backup holds the data that was replaced.
    undo = home.post(f"/api/settings/backups/{result['safety_backup']['name']}/restore")
    assert undo.status_code == 200
    assert appliance_names(home) == ["Added later"]


def test_the_app_keeps_working_after_a_restore(home: TestClient) -> None:
    backup = make_backup(home)
    home.post(f"/api/settings/backups/{backup['name']}/restore")

    assert home.get("/api/health").json()["status"] == "ok"
    assert home.post("/api/appliances", json=fixed_payload(name="After restore")).status_code == 201
    assert sorted(appliance_names(home)) == ["After restore", "Refrigerator"]
    assert home.get("/api/household").json()["name"] == "Test home"


def test_restore_from_an_uploaded_file(home: TestClient) -> None:
    backup = make_backup(home)
    data = home.get(f"/api/settings/backups/{backup['name']}").content
    home.post("/api/appliances", json=fixed_payload(name="Extra"))

    checked = home.post("/api/settings/restore/check", content=data, headers=BINARY)
    assert checked.status_code == 200 and checked.json()["appliances"] == 1
    assert sorted(appliance_names(home)) == ["Extra", "Refrigerator"]  # checking changes nothing

    restored = home.post("/api/settings/restore", content=data, headers=BINARY)

    assert restored.status_code == 200, restored.text
    assert appliance_names(home) == ["Refrigerator"]


def test_restore_leaves_no_temporary_files_behind(home: TestClient, settings_of: Settings) -> None:
    data = home.get(f"/api/settings/backups/{make_backup(home)['name']}").content
    home.post("/api/settings/restore/check", content=data, headers=BINARY)
    home.post("/api/settings/restore", content=data, headers=BINARY)
    home.post("/api/settings/restore", content=b"garbage", headers=BINARY)
    assert not [p for p in settings_of.data_dir.iterdir() if p.suffix == ".tmp"]


def test_an_older_backup_is_upgraded_after_restore_and_its_data_survives(
    home: TestClient, tmp_path: Path, settings_of: Settings
) -> None:
    old = old_database(tmp_path / "old.db", "0003")
    execute(
        old,
        "INSERT INTO household (name, occupants, max_load_kw, currency_code, time_format, created_at, updated_at) "
        "VALUES ('Old home', 2, 4, 'USD', '12h', '2025-01-01', '2025-01-01')",
    )

    checked = home.post(
        "/api/settings/restore/check", content=old.read_bytes(), headers=BINARY
    ).json()
    assert (
        checked["schema_revision"] == "0003"
        and checked["needs_upgrade"] is True
        and checked["household_name"] == "Old home"
    )

    restored = home.post("/api/settings/restore", content=old.read_bytes(), headers=BINARY)

    assert restored.status_code == 200, restored.text
    assert restored.json()["schema_revision"] == head_revision(build_alembic_config())
    assert home.get("/api/household").json()["name"] == "Old home"
    assert home.get("/api/simulations").json() == []  # tables added after 0003 now exist
    assert any(b["kind"] == "pre-migration" for b in home.get("/api/settings/backups").json())


# --- Invalid backups never touch the data ----------------------------------------------------------


def invalid_upload_cases(tmp_path: Path) -> dict[str, bytes]:
    newer = old_database(tmp_path / "newer.db", "0003")
    execute(newer, "UPDATE alembic_version SET version_num = '9999'")
    foreign = tmp_path / "foreign.db"
    execute(foreign, "CREATE TABLE contacts (id INTEGER PRIMARY KEY)")
    return {
        "not a database": b"%PDF-1.7 this is a pdf" * 100,
        "another app's database": foreign.read_bytes(),
        "newer version": newer.read_bytes(),
        "empty": b"",
    }


@pytest.mark.parametrize(
    "case", ["not a database", "another app's database", "newer version", "empty"]
)
def test_invalid_uploads_are_rejected_and_nothing_changes(
    home: TestClient, settings_of: Settings, tmp_path: Path, case: str
) -> None:
    payload = invalid_upload_cases(tmp_path)[case]
    backups_before = {b["name"] for b in home.get("/api/settings/backups").json()}

    for path in ("/api/settings/restore/check", "/api/settings/restore"):
        response = home.post(path, content=payload, headers=BINARY)
        assert response.status_code == 422, (path, response.text)
        assert error_fields(response)[
            "file"
        ]  # a plain-language reason, shown next to the file picker

    assert appliance_names(home) == ["Refrigerator"]
    assert {
        b["name"] for b in home.get("/api/settings/backups").json()
    } == backups_before  # no safety backup either
    assert "Traceback" not in response.text


def test_the_reason_names_the_problem(home: TestClient, tmp_path: Path) -> None:
    messages = {
        case: error_fields(home.post("/api/settings/restore", content=data, headers=BINARY))["file"]
        for case, data in invalid_upload_cases(tmp_path).items()
        if data
    }
    assert "not a SQLite database" in messages["not a database"]
    assert "not a PowerShift backup" in messages["another app's database"]
    assert "newer version" in messages["newer version"]


def test_a_damaged_stored_backup_cannot_be_restored(
    home: TestClient, settings_of: Settings
) -> None:
    backup = make_backup(home)
    path = settings_of.backups_dir / backup["name"]
    data = bytearray(path.read_bytes())
    for offset in range(4096, len(data), 97):
        data[offset] = (data[offset] + 1) % 256
    path.write_bytes(bytes(data))

    response = home.post(f"/api/settings/backups/{backup['name']}/restore")

    assert response.status_code == 422
    assert appliance_names(home) == ["Refrigerator"]


@pytest.mark.parametrize(
    "name",
    [
        "..%2Fpowershift.db",
        "%2E%2E%2Fpowershift.db",
        "..%5Cpowershift.db",
        "powershift.db",
        "manual.txt",
        "does-not-exist.db",
        "a%00b.db",
        "C%3A%5Cwindows%5Cwin.db",
    ],
)
def test_backup_names_cannot_escape_the_backups_folder(home: TestClient, name: str) -> None:
    for path in (f"/api/settings/backups/{name}", f"/api/settings/backups/{name}/check"):
        assert home.get(path).status_code == 404, path
    assert home.post(f"/api/settings/backups/{name}/restore").status_code == 404
    assert appliance_names(home) == ["Refrigerator"]


def test_oversized_uploads_are_refused_before_reading(home: TestClient) -> None:
    response = home.post(
        "/api/settings/restore",
        content=b"x",
        headers={**BINARY, "Content-Length": str(600 * 1024 * 1024)},
    )
    assert response.status_code in (413, 422, 400)  # the declared size alone is enough to refuse


# --- Export -------------------------------------------------------------------------------------------


def test_export_contains_the_users_data_in_readable_json(home: TestClient) -> None:
    home.post(
        "/api/simulations",
        json={"name": "Bigger limit", "changes": [{"type": "set_load_limit", "max_load_kw": 8}]},
    )

    response = home.get("/api/settings/export")

    assert response.status_code == 200
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="powershift-data-export.json"'
    )
    body = response.json()
    assert body["household"]["name"] == "Test home"
    assert [a["name"] for a in body["appliances"]] == ["Refrigerator"]
    assert (
        body["scenarios"][0]["name"] == "Bigger limit"
        and "latest_result" not in body["scenarios"][0]
    )
    assert body["schema_revision"] == head_revision(build_alembic_config())
    assert "restore" in body["note"].lower()
    assert set(body) >= {"exported_at", "app_version", "tariffs", "optimization_history"}


def test_export_of_an_empty_database(client: TestClient) -> None:
    body = client.get("/api/settings/export").json()
    assert body["household"] is None and body["appliances"] == [] and body["scenarios"] == []


# --- Reset ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"confirm": "reset"},
        {"confirm": "yes"},
        {"confirm": ""},
        {"confirm": "RESET", "extra": 1},
        {"confirm": True},
    ],
)
def test_reset_requires_the_exact_confirmation_word(home: TestClient, body: dict[str, Any]) -> None:
    assert home.post("/api/settings/reset", json=body).status_code == 422
    assert appliance_names(home) == ["Refrigerator"]
    assert not [b for b in home.get("/api/settings/backups").json() if b["kind"] == "pre-reset"]


def test_reset_deletes_everything_but_can_be_undone_from_the_safety_backup(
    client: TestClient,
) -> None:
    client.post("/api/demo")
    client.post("/api/optimization/run", json={"priority": "cost"})
    scenario = client.post("/api/simulations", json={"name": "S", "changes": []}).json()
    client.post(f"/api/simulations/{scenario['id']}/run")
    before = client.get("/api/settings/about").json()["counts"]
    assert all(count > 0 for count in before.values())

    response = client.post("/api/settings/reset", json={"confirm": "RESET"})

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["removed"] == {
        "appliances": 9,
        "tariffs": 1,
        "simulation_scenarios": 1,
        "optimization_runs": 1,
        "household": 1,
    }
    assert client.get("/api/settings/about").json()["counts"] == dict.fromkeys(before, 0)
    assert (
        client.get("/api/household").json() is None and client.get("/api/appliances").json() == []
    )
    assert (
        client.get("/api/simulations").json() == []
        and client.get("/api/optimization/history").json() == []
    )
    assert result["safety_backup"]["kind"] == "pre-reset"
    # After a reset the app is usable again...
    assert client.post("/api/demo").status_code == 201
    # ...and the old data can still be recovered from the safety backup.
    client.post("/api/settings/reset", json={"confirm": "RESET"})
    restored = client.post(f"/api/settings/backups/{result['safety_backup']['name']}/restore")
    assert restored.status_code == 200
    assert client.get("/api/settings/about").json()["counts"] == before


def test_reset_keeps_existing_backups(home: TestClient) -> None:
    backup = make_backup(home)
    home.post("/api/settings/reset", json={"confirm": "RESET"})
    assert backup["name"] in {b["name"] for b in home.get("/api/settings/backups").json()}


def test_failed_reset_deletes_nothing(
    home: TestClient, settings_of: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_: object, **__: object) -> None:
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr("powershift.services.data_service.backup_database", fail)

    response = home.post("/api/settings/reset", json={"confirm": "RESET"})

    assert (
        response.status_code == 500 and "nothing was deleted" in response.json()["error"]["message"]
    )
    assert appliance_names(home) == ["Refrigerator"]


def test_settings_endpoints_require_the_launch_token(
    settings_of: Settings, home: TestClient
) -> None:
    from fastapi.testclient import TestClient as Anonymous

    from powershift.main import create_app

    with Anonymous(create_app(settings_of)) as anonymous:
        for method, path in (
            ("get", "/api/settings/about"),
            ("get", "/api/settings/export"),
            ("post", "/api/settings/reset"),
        ):
            assert getattr(anonymous, method)(path).status_code == 401, path
    with closing(sqlite3.connect(settings_of.database_path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM appliances").fetchone()[0] == 1
