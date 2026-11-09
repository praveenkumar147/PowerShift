"""End-to-end check of the real backend process, exactly as the desktop shell runs it."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

from powershift.main import READY_PREFIX

STARTUP_TIMEOUT_SECONDS = 30


def test_backend_process_prints_ready_line_and_serves_health(tmp_path: Path) -> None:
    process = subprocess.Popen(
        [sys.executable, "-m", "powershift", "--data-dir", str(tmp_path), "--token", "t0k"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert process.stdout is not None
        ready_line = process.stdout.readline().strip()
        assert ready_line.startswith(f"{READY_PREFIX} port=")
        port = int(ready_line.split("=", 1)[1])

        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/health", headers={"X-PowerShift-Token": "t0k"}
        )
        with urllib.request.urlopen(request, timeout=STARTUP_TIMEOUT_SECONDS) as response:
            body = json.load(response)

        assert body["status"] == "ok"
        assert (tmp_path / "powershift.db").exists()
        assert (tmp_path / "logs" / "backend.log").exists()
    finally:
        process.terminate()
        process.wait(timeout=STARTUP_TIMEOUT_SECONDS)
