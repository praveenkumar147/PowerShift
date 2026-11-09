"""Health check used by the desktop shell to know the backend is ready."""

from __future__ import annotations

from fastapi import APIRouter

from powershift import __version__
from powershift.api.deps import SessionDep, SettingsDep
from powershift.db.migrate import revision_of
from powershift.schemas.health import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(session: SessionDep, settings: SettingsDep) -> HealthResponse:
    # Reading the Alembic revision is a real query, so it also proves the
    # database file is reachable and migrated.
    return HealthResponse(
        status="ok",
        version=__version__,
        schema_revision=revision_of(session.connection()),
        database_path=str(settings.database_path),
    )
