"""A write must be committed BEFORE the client is told it succeeded.

The UI refreshes its lists the moment a request succeeds. If the database commit happened
after the response was sent, that refresh could read old data, and a failed commit would
happen after the client had already been told "success". TestClient hides this (it waits for
all cleanup before returning), so this test watches the database at the exact moment the
response starts, using the ASGI interface directly.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import closing
from typing import Any

from powershift.core.config import Settings
from powershift.main import create_app
from tests.conftest import TEST_TOKEN, make_settings
from tests.factories import fixed_payload


def appliance_rows(settings: Settings) -> int:
    with closing(sqlite3.connect(settings.database_path)) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM appliances").fetchone()[0])


async def call(app: Any, method: str, path: str, body: dict[str, Any] | None, on_start: Any) -> int:
    payload = json.dumps(body).encode() if body is not None else b""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "scheme": "http",
        "server": ("127.0.0.1", 80),
        "client": ("127.0.0.1", 1),
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(payload)).encode()),
            (b"x-powershift-token", TEST_TOKEN.encode()),
        ],
    }
    status = 0

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": payload, "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]
            on_start()

    await app(scope, receive, send)
    return status


def test_data_is_committed_before_the_response_is_sent(tmp_path: Any) -> None:
    settings = make_settings(tmp_path)
    from powershift.main import prepare_database

    prepare_database(settings)
    app = create_app(settings)
    seen: dict[str, int] = {}

    status = asyncio.run(
        call(
            app,
            "POST",
            "/api/appliances",
            fixed_payload(),
            lambda: seen.update(created=appliance_rows(settings)),
        )
    )
    assert status == 201 and seen["created"] == 1, (
        "the new appliance was not committed when the 201 was sent"
    )

    appliance_id = 1
    status = asyncio.run(
        call(
            app,
            "DELETE",
            f"/api/appliances/{appliance_id}",
            None,
            lambda: seen.update(deleted=appliance_rows(settings)),
        )
    )
    assert status == 204 and seen["deleted"] == 0, (
        "the deletion was not committed when the 204 was sent"
    )
    app.state.engine.dispose()
