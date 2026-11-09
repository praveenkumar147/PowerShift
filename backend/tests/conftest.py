from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from powershift.core.config import Settings
from powershift.main import create_app, prepare_database

TEST_TOKEN = "test-token-123"


def make_settings(tmp_path: Path, token: str | None = TEST_TOKEN) -> Settings:
    settings = Settings(data_dir=tmp_path / "data", token=token)
    settings.ensure_directories()
    return settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = make_settings(tmp_path)
    prepare_database(settings)
    return settings


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app, headers={"X-PowerShift-Token": TEST_TOKEN}) as test_client:
        yield test_client
    app.state.engine.dispose()
