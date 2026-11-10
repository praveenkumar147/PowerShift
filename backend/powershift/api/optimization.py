"""Smart Scheduler endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, status

from powershift.api.deps import SessionDep
from powershift.schemas.optimization import (
    OptimizationRequest,
    OptimizationRunRead,
    OptimizationSummary,
)
from powershift.services.optimization_service import OptimizationService

router = APIRouter(prefix="/api/optimization", tags=["optimization"])


@router.post("/run", response_model=OptimizationRunRead, status_code=status.HTTP_201_CREATED)
def run_optimization(session: SessionDep, request: OptimizationRequest) -> OptimizationRunRead:
    """Solves with CP-SAT, validates the result independently, stores and returns the run.

    An infeasible problem is still a successful request: the stored run has status
    INFEASIBLE and a list of diagnostics.
    """
    return OptimizationService(session).run(request, date.today())


@router.get("/history", response_model=list[OptimizationSummary])
def optimization_history(session: SessionDep) -> list[OptimizationSummary]:
    """Most recent runs first (up to 50)."""
    return OptimizationService(session).history()


@router.get("/{run_id}", response_model=OptimizationRunRead)
def get_optimization_run(session: SessionDep, run_id: int) -> OptimizationRunRead:
    return OptimizationService(session).get(run_id)
