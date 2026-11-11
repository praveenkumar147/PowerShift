"""Response models for local data management (backups, restore, reset, about)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class BackupInfo(BaseModel):
    name: str
    kind: Literal["manual", "pre-migration", "pre-restore", "pre-reset", "other"]
    """Who made it: you (manual) or PowerShift as a safety copy before a risky step."""
    size_bytes: int
    created_at: datetime


class BackupSummary(BaseModel):
    """What a validated backup contains (shown before the user confirms a restore)."""

    size_bytes: int
    schema_revision: str
    needs_upgrade: bool
    """The backup is from an older version; it will be upgraded after the restore."""
    household_name: str | None
    appliances: int
    tariffs: int
    scenarios: int
    optimization_runs: int


class RestoreResult(BaseModel):
    restored: BackupSummary
    safety_backup: BackupInfo
    """A copy of the data that was replaced, so the restore can be undone."""
    schema_revision: str


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: Literal["RESET"]
    """Must be exactly RESET, so a reset can never happen by accident."""


class ResetResult(BaseModel):
    removed: dict[str, int]
    safety_backup: BackupInfo


class About(BaseModel):
    app_version: str
    schema_revision: str | None
    python_version: str
    solver: str
    data_dir: str
    database_path: str
    database_size_bytes: int
    backups_dir: str
    logs_dir: str
    counts: dict[str, int]
