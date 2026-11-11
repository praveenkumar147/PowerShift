"""Settings and local data management endpoints.

Everything here works on files in the user's own data folder; nothing leaves the computer.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse

from powershift.api.deps import EngineDep, SessionDep, SettingsDep
from powershift.core.errors import PayloadTooLargeError, ValidationFailedError
from powershift.db.backup import MAX_BACKUP_BYTES
from powershift.schemas.data import (
    About,
    BackupInfo,
    BackupSummary,
    Preferences,
    PreferencesUpdate,
    ResetRequest,
    ResetResult,
    RestoreResult,
)
from powershift.services.data_service import DataService
from powershift.services.preferences_service import PreferencesService

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _service(settings: SettingsDep, engine: EngineDep) -> DataService:
    return DataService(settings, engine)


async def _uploaded_bytes(request: Request) -> bytes:
    """The raw request body (the browser sends the chosen file as-is; no form parsing needed)."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BACKUP_BYTES:
        raise PayloadTooLargeError("The file is too large to be a PowerShift backup.")
    data = await request.body()
    if len(data) > MAX_BACKUP_BYTES:
        raise PayloadTooLargeError("The file is too large to be a PowerShift backup.")
    if not data:
        raise ValidationFailedError("No file was received.", {"file": "Choose a backup file."})
    return data


@router.get("/preferences", response_model=Preferences)
def get_preferences(session: SessionDep) -> Preferences:
    return PreferencesService(session).get()


@router.put("/preferences", response_model=Preferences)
def put_preferences(update: PreferencesUpdate, session: SessionDep) -> Preferences:
    return PreferencesService(session).update(update)


@router.get("/about", response_model=About)
def about(settings: SettingsDep, engine: EngineDep) -> About:
    return _service(settings, engine).about()


@router.get("/backups", response_model=list[BackupInfo])
def list_backups(settings: SettingsDep, engine: EngineDep) -> list[BackupInfo]:
    """Backups in the app's backups folder, newest first."""
    return _service(settings, engine).list_backups()


@router.post("/backup", response_model=BackupInfo, status_code=status.HTTP_201_CREATED)
def create_backup(settings: SettingsDep, engine: EngineDep) -> BackupInfo:
    return _service(settings, engine).create_backup()


@router.get("/backups/{name}")
def download_backup(name: str, settings: SettingsDep, engine: EngineDep) -> FileResponse:
    path = _service(settings, engine).backup_path(name)
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)


@router.get("/backups/{name}/check", response_model=BackupSummary)
def check_backup(name: str, settings: SettingsDep, engine: EngineDep) -> BackupSummary:
    """Validates a stored backup and says what it contains, without changing anything."""
    return _service(settings, engine).check_backup(name)


@router.post("/backups/{name}/restore", response_model=RestoreResult)
def restore_backup(name: str, settings: SettingsDep, engine: EngineDep) -> RestoreResult:
    """Validates, makes a safety backup of the current data, then replaces it."""
    return _service(settings, engine).restore_backup(name)


@router.post("/restore/check", response_model=BackupSummary)
async def check_upload(request: Request, settings: SettingsDep, engine: EngineDep) -> BackupSummary:
    """Validates an uploaded backup file (request body = the file) without changing anything."""
    data = await _uploaded_bytes(request)
    return await run_in_threadpool(_service(settings, engine).check_upload, data)


@router.post("/restore", response_model=RestoreResult)
async def restore_upload(
    request: Request, settings: SettingsDep, engine: EngineDep
) -> RestoreResult:
    """Validates an uploaded backup, makes a safety backup, then replaces the current data."""
    data = await _uploaded_bytes(request)
    return await run_in_threadpool(_service(settings, engine).restore_upload, data)


@router.get("/export")
def export_data(session: SessionDep, settings: SettingsDep, engine: EngineDep) -> JSONResponse:
    """A readable JSON copy of the user's data (household, appliances, tariffs, scenarios)."""
    content: dict[str, Any] = _service(settings, engine).export_data(session)
    return JSONResponse(
        content,
        headers={"Content-Disposition": 'attachment; filename="powershift-data-export.json"'},
    )


@router.post("/reset", response_model=ResetResult)
def reset_data(
    request: ResetRequest, session: SessionDep, settings: SettingsDep, engine: EngineDep
) -> ResetResult:
    """Deletes ALL user data after making a safety backup. Requires confirm = "RESET"."""
    return _service(settings, engine).reset(session)
