"""A report as plain data, independent of file format.

Every export (CSV, PDF) renders this same structure, so the formats cannot disagree.
Every report carries: a generation date, the units (in column headers), the relevant
tariff configuration, the calculation assumptions, and an explicit statement that the
figures are ESTIMATES from user-entered settings, not measurements.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

Cell = str | int | float | None

ESTIMATE_LABEL = (
    "ESTIMATED figures calculated from the appliance settings you entered. "
    "They are not measured consumption and not a utility bill."
)


@dataclass(frozen=True, slots=True)
class ReportTable:
    title: str | None
    columns: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]
    emphasise_last_row: bool = False
    """Used for a trailing total row."""


@dataclass(frozen=True, slots=True)
class Report:
    kind: str
    title: str
    generated_at: datetime
    household: str | None
    currency: str | None
    parameters: tuple[tuple[str, str], ...]
    tariff: tuple[tuple[str, str], ...]
    """The tariff configuration the figures depend on (empty if none applies)."""
    tables: tuple[ReportTable, ...]
    assumptions: tuple[str, ...]
    basis: str = ESTIMATE_LABEL

    @property
    def filename_stem(self) -> str:
        return f"powershift-{self.kind.replace('_', '-')}-{self.generated_at:%Y%m%d}"
