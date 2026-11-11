"""Simulation Lab endpoints.

Scenarios are what-if changes applied to copies of your data. Nothing here ever
modifies real appliances, tariffs or the household.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Response, status

from powershift.api.deps import SessionDep
from powershift.schemas.simulation import ScenarioInput, ScenarioRead, SimulationResultRead
from powershift.services.simulation_service import SimulationService

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


@router.get("", response_model=list[ScenarioRead])
def list_scenarios(session: SessionDep) -> list[ScenarioRead]:
    """Scenarios by name, each with its latest result."""
    return SimulationService(session).list_scenarios()


@router.post("", response_model=ScenarioRead, status_code=status.HTTP_201_CREATED)
def create_scenario(session: SessionDep, data: ScenarioInput) -> ScenarioRead:
    return SimulationService(session).create(data)


@router.get("/{scenario_id}", response_model=ScenarioRead)
def get_scenario(session: SessionDep, scenario_id: int) -> ScenarioRead:
    return SimulationService(session).get(scenario_id)


@router.put("/{scenario_id}", response_model=ScenarioRead)
def update_scenario(session: SessionDep, scenario_id: int, data: ScenarioInput) -> ScenarioRead:
    return SimulationService(session).update(scenario_id, data)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(session: SessionDep, scenario_id: int) -> Response:
    SimulationService(session).delete(scenario_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{scenario_id}/run", response_model=SimulationResultRead, status_code=status.HTTP_201_CREATED
)
def run_scenario(session: SessionDep, scenario_id: int) -> SimulationResultRead:
    """Analyses the scenario on copies of your data, stores and returns the result."""
    return SimulationService(session).run(scenario_id, date.today())


@router.get("/{scenario_id}/results", response_model=list[SimulationResultRead])
def scenario_results(session: SessionDep, scenario_id: int) -> list[SimulationResultRead]:
    """Previous results of a scenario, most recent first (up to 20)."""
    return SimulationService(session).results(scenario_id)
