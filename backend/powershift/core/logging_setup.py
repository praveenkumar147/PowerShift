"""Local file logging (no remote telemetry)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILENAME = "backend.log"
MAX_LOG_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3


def configure_logging(logs_dir: Path) -> None:
    file_handler = RotatingFileHandler(
        logs_dir / LOG_FILENAME,
        maxBytes=MAX_LOG_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[file_handler, logging.StreamHandler()],
        force=True,
    )
    # Alembic logs two INFO lines every time a revision is read (e.g. each health
    # check). Our own migrate module logs the migrations that actually happen.
    logging.getLogger("alembic.runtime.migration").setLevel(logging.WARNING)
