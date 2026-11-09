"""Household profile (exactly one row in the first version)."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from powershift.db.base import Base, TimestampMixin


class Household(TimestampMixin, Base):
    __tablename__ = "household"
    __table_args__ = (
        CheckConstraint("occupants >= 1", name="occupants_positive"),
        CheckConstraint("max_load_kw > 0", name="max_load_positive"),
        CheckConstraint("time_format IN ('12h', '24h')", name="time_format_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    occupants: Mapped[int] = mapped_column(Integer, nullable=False)
    location_label: Mapped[str | None] = mapped_column(String(100))
    max_load_kw: Mapped[float] = mapped_column(Float, nullable=False)
    """Household connection limit in kW (instantaneous power, not energy)."""
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    """ISO 4217 code, e.g. INR, USD. Display only; no conversion is performed."""
    time_format: Mapped[str] = mapped_column(String(3), nullable=False, default="24h")
