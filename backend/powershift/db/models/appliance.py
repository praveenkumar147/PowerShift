"""Appliance tables.

appliances                    one row per appliance
appliance_operating_days      which weekdays it is used (one row per weekday)
appliance_usage_blocks        on-periods of a FIXED appliance
appliance_flex_constraints    scheduling limits of a FLEXIBLE appliance (1:1)
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from powershift.db.base import Base, TimestampMixin
from powershift.domain.appliance import ApplianceCategory, ApplianceMode, Priority
from powershift.domain.time_window import MINUTES_PER_DAY


def _in_values(column: str, enum: type[ApplianceCategory | ApplianceMode | Priority]) -> str:
    values = ", ".join(f"'{member.value}'" for member in enum)
    return f"{column} IN ({values})"


START_MINUTE_RULE = f"BETWEEN 0 AND {MINUTES_PER_DAY - 1}"
END_MINUTE_RULE = f"BETWEEN 1 AND {MINUTES_PER_DAY}"


class Appliance(TimestampMixin, Base):
    __tablename__ = "appliances"
    __table_args__ = (
        CheckConstraint(_in_values("category", ApplianceCategory), name="category_valid"),
        CheckConstraint(_in_values("mode", ApplianceMode), name="mode_valid"),
        CheckConstraint(_in_values("priority", Priority), name="priority_valid"),
        CheckConstraint("rated_power_w > 0", name="rated_power_positive"),
        CheckConstraint("quantity >= 1", name="quantity_positive"),
        CheckConstraint("duty_cycle > 0 AND duty_cycle <= 1", name="duty_cycle_range"),
        Index("ix_appliances_category_mode", "category", "mode"),
        # Names are unique regardless of letter case ("Fridge" == "fridge").
        Index("uq_appliances_name_lower", func.lower("name"), unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    rated_power_w: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    duty_cycle: Mapped[float] = mapped_column(Float, nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    allow_simultaneous: Mapped[bool] = mapped_column(Boolean, nullable=False)

    operating_days: Mapped[list[ApplianceOperatingDay]] = relationship(
        back_populates="appliance",
        cascade="all, delete-orphan",
        order_by="ApplianceOperatingDay.weekday",
    )
    usage_blocks: Mapped[list[ApplianceUsageBlock]] = relationship(
        back_populates="appliance",
        cascade="all, delete-orphan",
        order_by="ApplianceUsageBlock.start_minute",
    )
    flex_constraint: Mapped[ApplianceFlexConstraint | None] = relationship(
        back_populates="appliance", cascade="all, delete-orphan", uselist=False
    )


class ApplianceOperatingDay(Base):
    __tablename__ = "appliance_operating_days"
    __table_args__ = (
        UniqueConstraint("appliance_id", "weekday"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appliance_id: Mapped[int] = mapped_column(
        ForeignKey("appliances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)

    appliance: Mapped[Appliance] = relationship(back_populates="operating_days")


class ApplianceUsageBlock(Base):
    __tablename__ = "appliance_usage_blocks"
    __table_args__ = (
        CheckConstraint(f"start_minute {START_MINUTE_RULE}", name="start_range"),
        CheckConstraint(f"end_minute {END_MINUTE_RULE}", name="end_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appliance_id: Mapped[int] = mapped_column(
        ForeignKey("appliances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)

    appliance: Mapped[Appliance] = relationship(back_populates="usage_blocks")


class ApplianceFlexConstraint(Base):
    __tablename__ = "appliance_flex_constraints"
    __table_args__ = (
        CheckConstraint(
            f"run_duration_minutes BETWEEN 1 AND {MINUTES_PER_DAY}", name="duration_range"
        ),
        CheckConstraint(f"earliest_start_minute {START_MINUTE_RULE}", name="earliest_range"),
        CheckConstraint(f"latest_end_minute {END_MINUTE_RULE}", name="latest_range"),
        CheckConstraint(f"current_start_minute {START_MINUTE_RULE}", name="current_range"),
        CheckConstraint(
            "(preferred_start_minute IS NULL) = (preferred_end_minute IS NULL)",
            name="preferred_both_or_neither",
        ),
    )

    # Primary key = foreign key: enforces at most one constraint row per appliance.
    appliance_id: Mapped[int] = mapped_column(
        ForeignKey("appliances.id", ondelete="CASCADE"), primary_key=True
    )
    run_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    earliest_start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    latest_end_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    current_start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    preferred_start_minute: Mapped[int | None] = mapped_column(Integer)
    preferred_end_minute: Mapped[int | None] = mapped_column(Integer)
    must_be_contiguous: Mapped[bool] = mapped_column(Boolean, nullable=False)

    appliance: Mapped[Appliance] = relationship(back_populates="flex_constraint")
