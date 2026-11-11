"""Local data management: backups, restore, reset, export and 'about'.

Safety rules:
- A backup must pass validation (db/backup.py) before it can replace anything.
- Before a restore or a reset, the current data is copied to the backups folder first.
- Backup names are checked so they can only ever refer to files inside the backups folder.
- Restore is atomic (SQLite online backup); reset runs in one transaction.
"""

from __future__ import annotations

import dataclasses
import platform
import re
import sqlite3
import tempfile
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult

from powershift import __version__
from powershift.core.config import Settings
from powershift.core.errors import NotFoundError, OperationFailedError, ValidationFailedError
from powershift.db.backup import InvalidBackupError, restore_into, validate_backup_file
from powershift.db.migrate import backup_database, current_revision, upgrade_to_head
from powershift.schemas.data import About, BackupInfo, BackupSummary, ResetResult, RestoreResult
from powershift.services.appliance_service import ApplianceService
from powershift.services.household_service import HouseholdService
from powershift.services.optimization_service import OptimizationService
from powershift.services.simulation_service import SimulationService
from powershift.services.tariff_service import TariffService

BACKUP_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.db$")
KINDS = ("manual", "pre-migration", "pre-restore", "pre-reset")
UPLOAD_PREFIX = "upload-"
UPLOAD_SUFFIX = ".tmp"

# Children before parents, so foreign keys are never violated while deleting.
RESET_ORDER = (
    "simulation_results",
    "simulation_scenarios",
    "optimization_run_items",
    "optimization_runs",
    "appliance_flex_constraints",
    "appliance_usage_blocks",
    "appliance_operating_days",
    "appliances",
    "tariff_charges",
    "tariff_slabs",
    "tariff_periods",
    "tariffs",
    "household",
    "app_settings",
)
REPORTED_IN_RESET = (
    "appliances",
    "tariffs",
    "simulation_scenarios",
    "optimization_runs",
    "household",
)
COUNTED = ("household", "appliances", "tariffs", "simulation_scenarios", "optimization_runs")

EXPORT_NOTE = (
    "A readable copy of your PowerShift data for archiving or analysis. "
    "To move or restore your data, use Create backup and Restore instead."
)


def _kind(name: str) -> str:
    return next((k for k in KINDS if name.startswith(k + "-")), "other")


class DataService:
    def __init__(self, settings: Settings, engine: Engine) -> None:
        self._settings = settings
        self._engine = engine

    # --- Backups ------------------------------------------------------------------------

    def _info(self, path: Path) -> BackupInfo:
        stat = path.stat()
        return BackupInfo(
            name=path.name,
            kind=_kind(path.name),  # type: ignore[arg-type]
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_mtime, UTC),
        )

    def list_backups(self) -> list[BackupInfo]:
        folder = self._settings.backups_dir
        files = [p for p in folder.glob("*.db") if p.is_file()] if folder.exists() else []
        return sorted((self._info(p) for p in files), key=lambda b: b.created_at, reverse=True)

    def create_backup(self) -> BackupInfo:
        try:
            path = backup_database(
                self._settings.database_path, self._settings.backups_dir, "manual"
            )
        except (OSError, sqlite3.Error) as exc:
            raise OperationFailedError(
                "The backup could not be created. Check the free disk space."
            ) from exc
        return self._info(path)

    def backup_path(self, name: str) -> Path:
        """Only plain file names inside the backups folder are accepted (no path traversal)."""
        folder = self._settings.backups_dir.resolve()
        candidate = (folder / name).resolve()
        if not BACKUP_NAME.fullmatch(name) or candidate.parent != folder or not candidate.is_file():
            raise NotFoundError("That backup does not exist.")
        return candidate

    # --- Validation and restore ------------------------------------------------------------

    @staticmethod
    def _validate(path: Path) -> BackupSummary:
        try:
            return BackupSummary(**dataclasses.asdict(validate_backup_file(path)))
        except InvalidBackupError as exc:
            raise ValidationFailedError(str(exc), {"file": str(exc)}) from exc

    def check_backup(self, name: str) -> BackupSummary:
        return self._validate(self.backup_path(name))

    def check_upload(self, data: bytes) -> BackupSummary:
        with self._temporary_file(data) as path:
            return self._validate(path)

    def restore_backup(self, name: str) -> RestoreResult:
        return self._restore(self.backup_path(name))

    def restore_upload(self, data: bytes) -> RestoreResult:
        with self._temporary_file(data) as path:
            return self._restore(path)

    def _restore(self, source: Path) -> RestoreResult:
        summary = self._validate(source)  # nothing is touched unless this passes
        settings = self._settings
        try:
            safety = backup_database(settings.database_path, settings.backups_dir, "pre-restore")
            restore_into(settings.database_path, source)
        except (OSError, sqlite3.Error) as exc:
            raise OperationFailedError(
                "The restore failed and your current data was not changed."
            ) from exc
        finally:
            self._engine.dispose()  # drop pooled connections; they may hold old pages
        try:
            upgrade_to_head(self._engine, settings.database_path, settings.backups_dir)
        except Exception as exc:
            raise OperationFailedError(
                "The data was restored but could not be upgraded to this version. "
                "Restore the 'pre-restore' backup to return to your previous data."
            ) from exc
        revision = current_revision(self._engine) or summary.schema_revision
        return RestoreResult(
            restored=summary, safety_backup=self._info(safety), schema_revision=revision
        )

    def _temporary_file(self, data: bytes) -> _TemporaryUpload:
        return _TemporaryUpload(self._settings.data_dir, data)

    # --- Reset ---------------------------------------------------------------------------------

    def reset(self, session: Session) -> ResetResult:
        """Deletes all user data: safety backup first, then one transaction."""
        settings = self._settings
        try:
            safety = backup_database(settings.database_path, settings.backups_dir, "pre-reset")
        except (OSError, sqlite3.Error) as exc:
            raise OperationFailedError(
                "A safety backup could not be created, so nothing was deleted."
            ) from exc
        removed: dict[str, int] = {}
        for table in RESET_ORDER:
            result = session.execute(text(f"DELETE FROM {table}"))
            deleted = cast("CursorResult[Any]", result).rowcount
            if table in REPORTED_IN_RESET:
                removed[table] = deleted
        return ResetResult(removed=removed, safety_backup=self._info(safety))

    # --- Export and about ---------------------------------------------------------------------

    def export_data(self, session: Session) -> dict[str, Any]:
        scenarios = [
            s.model_dump(mode="json", exclude={"latest_result"})
            for s in SimulationService(session).list_scenarios()
        ]
        household = HouseholdService(session).get()
        return {
            "exported_at": datetime.now(UTC).isoformat(),
            "app_version": __version__,
            "schema_revision": current_revision(self._engine),
            "note": EXPORT_NOTE,
            "household": household.model_dump(mode="json") if household else None,
            "appliances": [
                a.model_dump(mode="json") for a in ApplianceService(session).list(None, None, None)
            ],
            "tariffs": [t.model_dump(mode="json") for t in TariffService(session).list()],
            "scenarios": scenarios,
            "optimization_history": [
                h.model_dump(mode="json") for h in OptimizationService(session).history()
            ],
        }

    def about(self) -> About:
        settings = self._settings
        with self._engine.connect() as connection:
            counts = {
                table: int(connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
                for table in COUNTED
            }
        size = settings.database_path.stat().st_size if settings.database_path.exists() else 0
        return About(
            app_version=__version__,
            schema_revision=current_revision(self._engine),
            python_version=platform.python_version(),
            solver=f"OR-Tools CP-SAT {package_version('ortools')}",
            data_dir=str(settings.data_dir),
            database_path=str(settings.database_path),
            database_size_bytes=size,
            backups_dir=str(settings.backups_dir),
            logs_dir=str(settings.logs_dir),
            counts=counts,
        )


class _TemporaryUpload:
    """An uploaded file written next to the database, always removed afterwards."""

    def __init__(self, folder: Path, data: bytes) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=folder, prefix=UPLOAD_PREFIX, suffix=UPLOAD_SUFFIX, delete=False
        ) as handle:
            handle.write(data)
        self._path = Path(handle.name)

    def __enter__(self) -> Path:
        return self._path

    def __exit__(self, *_: object) -> None:
        self._path.unlink(missing_ok=True)
