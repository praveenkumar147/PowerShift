"""Application preferences (exactly one row)."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from powershift.db.base import Base, TimestampMixin


class AppSettings(TimestampMixin, Base):
    __tablename__ = "app_settings"
    __table_args__ = (
        CheckConstraint("theme IN ('system', 'light', 'dark')", name="theme_valid"),
        CheckConstraint(
            "default_optimization_priority IN ('cost', 'peak', 'balanced')",
            name="priority_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    theme: Mapped[str] = mapped_column(String(10), nullable=False, default="system")
    default_optimization_priority: Mapped[str] = mapped_column(
        String(10), nullable=False, default="balanced"
    )
