"""The PyInstaller-frozen backend (what the installer ships) behaves like the source backend.

Skipped unless it has been built (`powershell -File scripts/build-backend.ps1`). When it exists it
must run migrations, solve with CP-SAT and write a PDF: the three things a freezing mistake
(a missing data file or native library) silently breaks.
"""

from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from powershift.main import READY_PREFIX

FROZEN = (
    Path(__file__).resolve().parents[2] / "dist" / "powershift-backend" / "powershift-backend.exe"
)
TOKEN = "frozen-test"

pytestmark = pytest.mark.skipif(not FROZEN.exists(), reason="frozen backend not built")


def call(
    port: int, method: str, path: str, body: dict[str, Any] | None = None
) -> tuple[int, bytes]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method=method,
        headers={"X-PowerShift-Token": TOKEN, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.status, response.read()


def test_frozen_backend_migrates_solves_and_exports_pdf(tmp_path: Path) -> None:
    process = subprocess.Popen(
        [str(FROZEN), "--data-dir", str(tmp_path), "--port", "0", "--token", TOKEN],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert process.stdout is not None
        ready = process.stdout.readline().strip()
        assert ready.startswith(f"{READY_PREFIX} port="), ready
        port = int(ready.split("=", 1)[1])

        status, body = call(port, "GET", "/api/health")
        assert status == 200 and json.loads(body)["schema_revision"] is not None  # migrations ran

        assert call(port, "POST", "/api/demo")[0] == 201
        status, body = call(
            port,
            "POST",
            "/api/optimization/run",
            {
                "priority": "cost",
                "balance_weight": 50,
                "start_step_minutes": 30,
                "time_limit_seconds": 10,
            },
        )
        run = json.loads(body)
        assert (
            status == 201 and run["status"] == "OPTIMAL" and run["schedule_valid"] is True
        )  # CP-SAT works

        status, body = call(
            port,
            "POST",
            "/api/reports/export",
            {"type": "bill_estimate", "format": "pdf", "params": {}},
        )
        assert status == 200 and body.startswith(b"%PDF-")  # ReportLab works

        status, body = call(port, "POST", "/api/settings/backup")
        assert status == 201  # SQLite backup works
    finally:
        process.terminate()
        process.wait(timeout=30)
