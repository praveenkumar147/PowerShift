"""Alembic environment.

Used both by the app at startup (connection passed in via config.attributes) and by
the `alembic` command line during development (connection created from the URL).
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import Connection, engine_from_config, pool

import powershift.db.models  # noqa: F401  (registers every table)
from powershift.db.base import Base

config = context.config
target_metadata = Base.metadata


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite needs table rebuilds for most ALTERs
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return

    engine = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with engine.connect() as new_connection:
        _run(new_connection)


if context.is_offline_mode():
    raise RuntimeError("Offline SQL generation is not supported for PowerShift.")
run_migrations_online()
