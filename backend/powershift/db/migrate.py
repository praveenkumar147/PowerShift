"""Run Alembic migrations automatically at startup.

The packaged app has no terminal, so the backend upgrades its own database to the
latest schema every time it starts. Before changing an existing database it makes a
copy in the backups folder, so a failed or buggy migration can never lose user data.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def build_alembic_config() -> Config:
    # No sqlalchemy.url here: upgrade_to_head() hands Alembic an open connection.
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


def head_revision(config: Config) -> str | None:
    return ScriptDirectory.from_config(config).get_current_head()


def revision_of(connection: Connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return revision_of(connection)


def backup_database(database_path: Path, backups_dir: Path, label: str) -> Path:
    """Copy the database with SQLite's online backup API (safe even in WAL mode)."""
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = backups_dir / f"{label}-{stamp}.db"
    with sqlite3.connect(database_path) as source, sqlite3.connect(target) as destination:
        source.backup(destination)
    return target


def upgrade_to_head(engine: Engine, database_path: Path, backups_dir: Path) -> str | None:
    """Upgrade the schema; returns the revision the database is at afterwards."""
    config = build_alembic_config()
    target = head_revision(config)
    current = current_revision(engine)

    if current == target:
        return current

    if current is not None:
        backup = backup_database(database_path, backups_dir, f"pre-migration-{current}")
        logger.info("Backed up database to %s before migrating", backup)

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    logger.info("Database migrated from %s to %s", current, target)
    return target
