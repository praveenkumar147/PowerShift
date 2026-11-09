from __future__ import annotations

from fastapi import APIRouter, status

from powershift.api.deps import SessionDep
from powershift.services.demo_service import DemoService

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("", status_code=status.HTTP_201_CREATED)
def load_sample_data(session: SessionDep) -> dict[str, int]:
    """Loads clearly labelled sample data. Only allowed when the database is empty (else 409)."""
    return DemoService(session).load()
