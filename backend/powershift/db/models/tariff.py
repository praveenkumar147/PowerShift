"""Tariff tables.

tariffs           one row per tariff; at most one is active
tariff_periods    time-of-use price periods
tariff_slabs      consumption bands (ordered by position)
tariff_charges    fixed, per-kWh and percentage charges (ordered by position)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from powershift.db.base import Base, TimestampMixin
from powershift.db.models.appliance import END_MINUTE_RULE, START_MINUTE_RULE
from powershift.domain.tariff import ChargeKind, DayType, SlabMode, TariffType

# Numeric(precision, scale): stored exactly, no floating-point rounding.
MONEY = Numeric(14, 4)
ENERGY = Numeric(14, 3)


def _in_values(column: str, enum: type[TariffType | DayType | SlabMode | ChargeKind]) -> str:
    return f"{column} IN ({', '.join(repr(m.value) for m in enum)})"


class Tariff(TimestampMixin, Base):
    __tablename__ = "tariffs"
    __table_args__ = (
        CheckConstraint(_in_values("tariff_type", TariffType), name="type_valid"),
        CheckConstraint(_in_values("slab_mode", SlabMode), name="slab_mode_valid"),
        CheckConstraint("flat_rate_per_kwh IS NULL OR flat_rate_per_kwh >= 0", name="flat_rate"),
        # Partial unique index: many rows may be inactive, only one may be active.
        Index(
            "uq_tariffs_single_active", "is_active", unique=True, sqlite_where=text("is_active = 1")
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    tariff_type: Mapped[str] = mapped_column(String(10), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    flat_rate_per_kwh: Mapped[Decimal | None] = mapped_column(MONEY)
    slab_mode: Mapped[str] = mapped_column(String(15), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    periods: Mapped[list[TariffPeriod]] = relationship(
        cascade="all, delete-orphan", order_by="TariffPeriod.position"
    )
    slabs: Mapped[list[TariffSlab]] = relationship(
        cascade="all, delete-orphan", order_by="TariffSlab.position"
    )
    charges: Mapped[list[TariffCharge]] = relationship(
        cascade="all, delete-orphan", order_by="TariffCharge.position"
    )


class TariffPeriod(Base):
    __tablename__ = "tariff_periods"
    __table_args__ = (
        CheckConstraint(f"start_minute {START_MINUTE_RULE}", name="start_range"),
        CheckConstraint(f"end_minute {END_MINUTE_RULE}", name="end_range"),
        CheckConstraint(_in_values("day_type", DayType), name="day_type_valid"),
        CheckConstraint("rate_per_kwh >= 0", name="rate_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tariff_id: Mapped[int] = mapped_column(
        ForeignKey("tariffs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    day_type: Mapped[str] = mapped_column(String(10), nullable=False)
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_per_kwh: Mapped[Decimal] = mapped_column(MONEY, nullable=False)


class TariffSlab(Base):
    __tablename__ = "tariff_slabs"
    __table_args__ = (
        CheckConstraint("up_to_kwh IS NULL OR up_to_kwh > 0", name="limit_positive"),
        CheckConstraint("rate_per_kwh >= 0", name="rate_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tariff_id: Mapped[int] = mapped_column(
        ForeignKey("tariffs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    up_to_kwh: Mapped[Decimal | None] = mapped_column(ENERGY)
    rate_per_kwh: Mapped[Decimal] = mapped_column(MONEY, nullable=False)


class TariffCharge(Base):
    __tablename__ = "tariff_charges"
    __table_args__ = (
        CheckConstraint(_in_values("kind", ChargeKind), name="kind_valid"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        CheckConstraint("kind != 'percentage' OR amount <= 100", name="percentage_max"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tariff_id: Mapped[int] = mapped_column(
        ForeignKey("tariffs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(15), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
