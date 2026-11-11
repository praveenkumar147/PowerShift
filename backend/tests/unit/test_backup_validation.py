"""Backup validation: every way a file can be unfit to replace the user's data."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import create_engine

from powershift.db.backup import (
    InvalidBackupError,
    known_revisions,
    restore_into,
    validate_backup_file,
)
from powershift.db.migrate import backup_database, build_alembic_config
from powershift.main import prepare_database
from tests.conftest import make_settings


@pytest.fixture
def good_backup(tmp_path: Path) -> Path:
    settings = make_settings(tmp_path)
    prepare_database(settings)
    return backup_database(settings.database_path, settings.backups_dir, "manual")


def execute(path: Path, *statements: str, foreign_keys: bool = True) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(f"PRAGMA foreign_keys={'ON' if foreign_keys else 'OFF'}")
        for statement in statements:
            connection.execute(statement)
        connection.commit()


def old_database(path: Path, revision: str) -> Path:
    """A real database as an older version of PowerShift would have written it."""
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    config = build_alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)
    engine.dispose()
    return path


def reason(path: Path) -> str:
    with pytest.raises(InvalidBackupError) as caught:
        validate_backup_file(path)
    return str(caught.value)


def test_a_valid_backup_is_summarised(good_backup: Path) -> None:
    summary = validate_backup_file(good_backup)

    _, head = known_revisions()
    assert summary.schema_revision == head and summary.needs_upgrade is False
    assert (summary.appliances, summary.tariffs, summary.scenarios, summary.optimization_runs) == (
        0,
        0,
        0,
        0,
    )
    assert summary.household_name is None and summary.size_bytes == good_backup.stat().st_size


def test_backups_are_single_self_contained_files(good_backup: Path) -> None:
    validate_backup_file(good_backup)
    assert sorted(p.name for p in good_backup.parent.iterdir()) == [
        good_backup.name
    ]  # no -wal / -shm


def test_counts_and_household_name_come_from_the_file(good_backup: Path) -> None:
    execute(
        good_backup,
        "INSERT INTO household (name, occupants, max_load_kw, currency_code, time_format, created_at, updated_at) "
        "VALUES ('Sharma home', 3, 5, 'INR', '24h', '2026-01-01', '2026-01-01')",
    )
    summary = validate_backup_file(good_backup)
    assert summary.household_name == "Sharma home"


def test_missing_or_empty_files_are_rejected(tmp_path: Path) -> None:
    assert reason(tmp_path / "nothing.db") == "The file is empty."
    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")
    assert reason(empty) == "The file is empty."


@pytest.mark.parametrize(
    "content",
    [b"%PDF-1.7 not a database at all" * 50, b"just some text\n" * 100, bytes(range(256)) * 20],
)
def test_files_that_are_not_sqlite_are_rejected(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "fake.db"
    path.write_bytes(content)
    assert "not a SQLite database" in reason(path)


def test_truncated_backups_are_rejected(good_backup: Path, tmp_path: Path) -> None:
    data = good_backup.read_bytes()
    truncated = tmp_path / "truncated.db"
    truncated.write_bytes(data[: len(data) // 2])
    assert reason(truncated)  # damaged, integrity failure or missing tables: never accepted


def test_corrupted_pages_are_rejected(good_backup: Path, tmp_path: Path) -> None:
    data = bytearray(good_backup.read_bytes())
    for offset in range(4096, len(data), 97):  # damage the body but keep the header
        data[offset] = (data[offset] + 1) % 256
    damaged = tmp_path / "damaged.db"
    damaged.write_bytes(bytes(data))
    assert reason(damaged)


def test_a_sqlite_file_that_is_not_a_powershift_database_is_rejected(tmp_path: Path) -> None:
    other = tmp_path / "other.db"
    execute(other, "CREATE TABLE contacts (id INTEGER PRIMARY KEY, name TEXT)")
    message = reason(other)
    assert message.startswith("This is not a PowerShift backup (missing:")
    assert "appliances" in message and "household" in message


def test_a_backup_from_a_newer_version_is_refused(good_backup: Path) -> None:
    execute(good_backup, "UPDATE alembic_version SET version_num = '9999'")
    message = reason(good_backup)
    assert "newer version" in message and "9999" in message


@pytest.mark.parametrize(
    "statement", ["DELETE FROM alembic_version", "INSERT INTO alembic_version VALUES ('0001')"]
)
def test_the_schema_version_must_be_recorded_exactly_once(
    good_backup: Path, statement: str
) -> None:
    execute(good_backup, statement, foreign_keys=False)
    assert "single schema version" in reason(good_backup)


def test_broken_references_are_rejected(good_backup: Path) -> None:
    execute(
        good_backup,
        "INSERT INTO appliance_operating_days (appliance_id, weekday) VALUES (999, 1)",
        foreign_keys=False,
    )
    assert "point to missing data" in reason(good_backup)


def test_an_older_backup_is_accepted_and_flagged_for_upgrade(tmp_path: Path) -> None:
    summary = validate_backup_file(old_database(tmp_path / "old.db", "0003"))
    assert summary.schema_revision == "0003" and summary.needs_upgrade is True


def test_validation_never_modifies_the_file(good_backup: Path) -> None:
    before = good_backup.read_bytes()
    validate_backup_file(good_backup)
    assert good_backup.read_bytes() == before


def test_restore_into_replaces_the_contents_of_a_live_database(
    tmp_path: Path, good_backup: Path
) -> None:
    live = tmp_path / "live.db"
    execute(live, "CREATE TABLE junk (x INTEGER)", "INSERT INTO junk VALUES (1)")

    restore_into(live, good_backup)

    with closing(sqlite3.connect(live)) as connection:
        tables = {
            r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "junk" not in tables and "appliances" in tables
