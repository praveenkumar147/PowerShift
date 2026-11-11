"""Validating and restoring database backups.

A backup is a copy of the SQLite file. Before one may replace the live data it must pass
every check below; any failure stops the restore with a plain-language reason and nothing
is changed.

Checks (in order, cheapest first):
1. The file exists, is not empty and is not absurdly large.
2. It starts with the SQLite file header (so a PDF renamed to .db is rejected at once).
3. SQLite can open it read-only and its own integrity check passes (not truncated/corrupt).
4. It has the PowerShift tables, and exactly one schema revision recorded.
5. That revision is one this version of PowerShift knows. A backup from a NEWER version
   is refused (it may contain columns this version would lose); an OLDER one is accepted
   and upgraded after the restore.
6. No row points at a row that does not exist (foreign key check).

Restoring copies the pages with SQLite's online backup API, which is atomic: either the
whole database is replaced or nothing is.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from alembic.script import ScriptDirectory

from powershift.db.migrate import build_alembic_config

SQLITE_HEADER = b"SQLite format 3\x00"
MAX_BACKUP_BYTES = 500 * 1024 * 1024
REQUIRED_TABLES = frozenset(
    {"alembic_version", "household", "app_settings", "appliances", "tariffs"}
)
COUNTED_TABLES = {
    "appliances": "appliances",
    "tariffs": "tariffs",
    "scenarios": "simulation_scenarios",
    "optimization_runs": "optimization_runs",
}


class InvalidBackupError(Exception):
    """The file cannot safely replace the current data. The message is shown to the user."""


@dataclass(frozen=True, slots=True)
class BackupSummary:
    size_bytes: int
    schema_revision: str
    needs_upgrade: bool
    household_name: str | None
    appliances: int
    tariffs: int
    scenarios: int
    optimization_runs: int


def known_revisions() -> tuple[set[str], str]:
    """(every schema revision this version has a migration for, the newest)"""
    script = ScriptDirectory.from_config(build_alembic_config())
    revisions = {revision.revision for revision in script.walk_revisions()}
    head = script.get_current_head()
    assert head is not None
    return revisions, head


def _open_read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def validate_backup_file(path: Path) -> BackupSummary:
    size = path.stat().st_size if path.exists() else 0
    if size == 0:
        raise InvalidBackupError("The file is empty.")
    if size > MAX_BACKUP_BYTES:
        raise InvalidBackupError("The file is too large to be a PowerShift backup.")
    with path.open("rb") as handle:
        if handle.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
            raise InvalidBackupError(
                "This is not a PowerShift backup: the file is not a SQLite database."
            )

    try:
        connection = _open_read_only(path)
    except sqlite3.Error as exc:
        raise InvalidBackupError("The file could not be opened as a database.") from exc
    try:
        return _check_open_database(connection, size)
    except sqlite3.DatabaseError as exc:
        raise InvalidBackupError("The file is damaged and cannot be read as a database.") from exc
    finally:
        connection.close()


def _count(connection: sqlite3.Connection, tables: set[str], table: str) -> int:
    if table not in tables:
        return 0
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def _check_open_database(connection: sqlite3.Connection, size: int) -> BackupSummary:
    if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise InvalidBackupError("The backup failed its integrity check; it is damaged.")

    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    missing = sorted(REQUIRED_TABLES - tables)
    if missing:
        raise InvalidBackupError(
            "This is not a PowerShift backup (missing: " + ", ".join(missing) + ")."
        )

    revisions = connection.execute("SELECT version_num FROM alembic_version").fetchall()
    if len(revisions) != 1:
        raise InvalidBackupError("The backup does not record a single schema version.")
    revision = str(revisions[0][0])
    known, head = known_revisions()
    if revision not in known:
        raise InvalidBackupError(
            f"This backup was made by a different or newer version of PowerShift "
            f"(schema {revision}). "
            "Update PowerShift to restore it."
        )

    if connection.execute("PRAGMA foreign_key_check").fetchall():
        raise InvalidBackupError("The backup contains records that point to missing data.")

    household = connection.execute("SELECT name FROM household LIMIT 1").fetchone()
    counts = {key: _count(connection, tables, table) for key, table in COUNTED_TABLES.items()}
    return BackupSummary(
        size_bytes=size,
        schema_revision=revision,
        needs_upgrade=revision != head,
        household_name=household[0] if household else None,
        **counts,
    )


def restore_into(live_database: Path, source: Path) -> None:
    """Replaces the contents of the live database with the source file, atomically."""
    reader = _open_read_only(source)
    writer = sqlite3.connect(live_database)
    try:
        reader.backup(writer)
    finally:
        reader.close()
        writer.close()
