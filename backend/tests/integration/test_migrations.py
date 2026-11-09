from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic.util.exc import CommandError
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from powershift.db.migrate import current_revision, upgrade_to_head
from powershift.db.session import create_db_engine
from powershift.main import prepare_database
from tests.conftest import make_settings


def test_fresh_database_is_created_with_expected_tables(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)

    prepare_database(settings)

    assert settings.database_path.exists()
    engine = create_db_engine(settings.database_url)
    tables = set(inspect(engine).get_table_names())
    assert {"household", "app_settings", "alembic_version"} <= tables
    engine.dispose()


def test_migration_is_idempotent_and_makes_no_backup_when_up_to_date(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    prepare_database(settings)
    engine = create_db_engine(settings.database_url)
    revision = current_revision(engine)

    result = upgrade_to_head(engine, settings.database_path, settings.backups_dir)

    assert result == revision
    assert list(settings.backups_dir.iterdir()) == []
    engine.dispose()


def test_existing_database_is_backed_up_before_migrating(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    prepare_database(settings)
    # Simulate an older schema version so the next start has to migrate.
    with sqlite3.connect(settings.database_path) as raw:
        raw.execute("DROP TABLE household")
        raw.execute("DROP TABLE app_settings")
        raw.execute("UPDATE alembic_version SET version_num = 'old'")
    engine = create_db_engine(settings.database_url)

    with pytest.raises(CommandError):  # unknown revision 'old' cannot be upgraded
        upgrade_to_head(engine, settings.database_path, settings.backups_dir)

    backups = list(settings.backups_dir.iterdir())
    assert len(backups) == 1
    assert backups[0].name.startswith("pre-migration-old-")
    engine.dispose()


def test_foreign_keys_and_wal_are_enabled(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    prepare_database(settings)
    engine = create_db_engine(settings.database_url)

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert connection.execute(text("PRAGMA journal_mode")).scalar() == "wal"
    engine.dispose()


def test_check_constraints_reject_impossible_household(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    prepare_database(settings)
    engine = create_db_engine(settings.database_url)

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO household (name, occupants, max_load_kw, currency_code, "
                "time_format, created_at, updated_at) "
                "VALUES ('Home', 0, 5, 'INR', '24h', '2026-01-01', '2026-01-01')"
            )
        )
    engine.dispose()
