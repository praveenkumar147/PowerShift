"""The theme preference is stored in the database and survives reset/restore rules."""

from __future__ import annotations

import sqlite3
from contextlib import closing

from fastapi.testclient import TestClient

from powershift.core.config import Settings


def stored_themes(settings: Settings) -> list[str]:
    with closing(sqlite3.connect(settings.database_path)) as connection:
        return [row[0] for row in connection.execute("SELECT theme FROM app_settings")]


def test_default_is_system_and_nothing_is_written_by_reading(client: TestClient) -> None:
    assert client.get("/api/settings/preferences").json() == {"theme": "system"}
    assert stored_themes(client.app.state.settings) == []  # type: ignore[attr-defined]


def test_the_choice_is_saved_in_the_database_and_updates_one_row(client: TestClient) -> None:
    assert client.put("/api/settings/preferences", json={"theme": "dark"}).json() == {
        "theme": "dark"
    }
    assert client.put("/api/settings/preferences", json={"theme": "light"}).status_code == 200
    assert client.get("/api/settings/preferences").json() == {"theme": "light"}
    assert stored_themes(client.app.state.settings) == ["light"]  # type: ignore[attr-defined]


def test_invalid_themes_and_extra_fields_are_rejected(client: TestClient) -> None:
    assert client.put("/api/settings/preferences", json={"theme": "purple"}).status_code == 422
    assert (
        client.put("/api/settings/preferences", json={"theme": "dark", "x": 1}).status_code == 422
    )
    assert client.put("/api/settings/preferences", json={}).status_code == 422
    assert client.get("/api/settings/preferences").json() == {"theme": "system"}


def test_reset_returns_the_theme_to_the_default(client: TestClient) -> None:
    client.put("/api/settings/preferences", json={"theme": "dark"})
    assert client.post("/api/settings/reset", json={"confirm": "RESET"}).status_code == 200
    assert client.get("/api/settings/preferences").json() == {"theme": "system"}
