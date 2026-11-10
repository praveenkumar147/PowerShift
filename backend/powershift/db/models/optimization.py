"""Optimization history.

optimization_runs        one row per solver run, with everything needed to
                         reproduce or investigate it (inputs snapshot, settings,
                         seed, versions) and the full result.
optimization_run_items   the scheduled tasks of a run (one per flexible appliance).
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
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from powershift.db.base import Base, utc_now
from powershift.db.models.appliance import END_MINUTE_RULE, START_MINUTE_RULE

MONEY = Numeric(14, 2)


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"
    __table_args__ = (
        CheckConstraint("priority IN ('cost', 'peak', 'balanced')", name="priority_valid"),
        CheckConstraint(
            "status IN ('OPTIMAL', 'FEASIBLE', 'INFEASIBLE', 'UNKNOWN', 'MODEL_INVALID')",
            name="status_valid",
        ),
        CheckConstraint("balance_weight BETWEEN 0 AND 100", name="weight_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    # Settings
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    balance_weight: Mapped[int] = mapped_column(Integer, nullable=False)
    start_step_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    time_limit_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    app_version: Mapped[str] = mapped_column(String(20), nullable=False)
    solver_version: Mapped[str] = mapped_column(String(40), nullable=False)
    # Outcome
    status: Mapped[str] = mapped_column(String(15), nullable=False)
    schedule_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    solve_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    moved_count: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_bill: Mapped[Decimal | None] = mapped_column(MONEY)
    optimized_bill: Mapped[Decimal | None] = mapped_column(MONEY)
    baseline_peak_kw: Mapped[float] = mapped_column(Float, nullable=False)
    optimized_peak_kw: Mapped[float | None] = mapped_column(Float)
    # Reproducibility: exactly what the solver was given, and the full result returned.
    inputs_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)

    items: Mapped[list[OptimizationRunItem]] = relationship(
        cascade="all, delete-orphan", order_by="OptimizationRunItem.id"
    )


class OptimizationRunItem(Base):
    __tablename__ = "optimization_run_items"
    __table_args__ = (
        CheckConstraint(f"start_minute {START_MINUTE_RULE}", name="start_range"),
        CheckConstraint(f"end_minute {END_MINUTE_RULE}", name="end_range"),
        CheckConstraint(f"baseline_start_minute {START_MINUTE_RULE}", name="baseline_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("optimization_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Kept (as NULL) if the appliance is deleted later; the name preserves history.
    appliance_id: Mapped[int | None] = mapped_column(
        ForeignKey("appliances.id", ondelete="SET NULL"), index=True
    )
    appliance_name: Mapped[str] = mapped_column(String(100), nullable=False)
    baseline_start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)
