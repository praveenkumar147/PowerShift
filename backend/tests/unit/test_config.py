from __future__ import annotations

from pathlib import Path

import pytest

from powershift.core.config import parse_settings


def test_parse_settings_reads_arguments(tmp_path: Path) -> None:
    settings = parse_settings(["--data-dir", str(tmp_path), "--port", "8123", "--token", "abc"])

    assert settings.data_dir == tmp_path.resolve()
    assert settings.port == 8123
    assert settings.token == "abc"
    assert settings.database_path == tmp_path.resolve() / "powershift.db"
    assert settings.database_url.startswith("sqlite:///")


def test_defaults_pick_free_port_and_no_token(tmp_path: Path) -> None:
    settings = parse_settings(["--data-dir", str(tmp_path)])

    assert settings.port == 0
    assert settings.token is None


def test_invalid_port_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        parse_settings(["--data-dir", str(tmp_path), "--port", "70000"])
