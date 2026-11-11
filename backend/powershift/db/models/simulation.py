"""Simulation Lab tables.

simulation_scenarios   a scenario = name + goal + a list of what-if CHANGES (JSON).
                       It never contains or modifies real appliances or tariffs.
simulation_results     one row per run of a scenario, with key numbers in columns
                       (for querying) and the full result as JSON (to show it exactly
                       as it was when run).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from powershift.db.base import Base, TimestampMixin, utc_now

MONEY = Numeric(14, 2)


class SimulationScenario(TimestampMixin, Base):
    __tablename__ = "simulation_scenarios"
    __table_args__ = (
        CheckConstraint("priority IN ('cost', 'peak', 'balanced')", name="priority_valid"),
        CheckConstraint("balance_weight BETWEEN 0 AND 100", name="weight_range"),
        # Names are unique regardless of letter case, so comparison columns are unambiguous.
        Index("uq_simulation_scenarios_name_lower", func.lower("name"), unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    balance_weight: Mapped[int] = mapped_column(Integer, nullable=False)
    changes_json: Mapped[str] = mapped_column(Text, nullable=False)


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    status: Mapped[str | None] = mapped_column(String(15))
    """Solver status, or NULL when optimisation was not attempted."""
    schedule_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    baseline_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    scenario_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_bill: Mapped[Decimal | None] = mapped_column(MONEY)
    scenario_bill: Mapped[Decimal | None] = mapped_column(MONEY)
    optimized_bill: Mapped[Decimal | None] = mapped_column(MONEY)
    baseline_peak_kw: Mapped[float] = mapped_column(Float, nullable=False)
    scenario_peak_kw: Mapped[float] = mapped_column(Float, nullable=False)
    optimized_peak_kw: Mapped[float | None] = mapped_column(Float)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
