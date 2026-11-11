"""CSV rendering.

- UTF-8 with a byte-order mark, so Excel shows non-English appliance names correctly.
- Several small tables in one file, each with a title row and separated by a blank line;
  numbers stay numeric (units are in the column headers) so the file remains machine-readable.
- Text cells that spreadsheets would treat as formulas ("=", "+", "-", "@") are neutralised,
  because appliance and scenario names are typed by the user ("CSV injection").
"""

from __future__ import annotations

import csv
import io

from powershift.reports.model import Cell, Report

BOM = "﻿"
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: Cell) -> str | int | float:
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(FORMULA_STARTS):
        return "'" + value
    return value


def render_csv(report: Report) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")

    writer.writerow(["PowerShift report"])
    writer.writerow([safe_cell(report.title)])
    writer.writerow(["Generated", f"{report.generated_at:%Y-%m-%d %H:%M} UTC"])
    if report.household:
        writer.writerow(["Household", safe_cell(report.household)])
    if report.currency:
        writer.writerow(["Currency", report.currency])
    writer.writerow(["Basis", report.basis])
    for label, value in report.parameters:
        writer.writerow([safe_cell(label), safe_cell(value)])
    if report.tariff:
        writer.writerow([])
        writer.writerow(["Tariff configuration"])
        for label, value in report.tariff:
            writer.writerow([safe_cell(label), safe_cell(value)])

    for table in report.tables:
        writer.writerow([])
        if table.title:
            writer.writerow([safe_cell(table.title)])
        writer.writerow([safe_cell(column) for column in table.columns])
        for row in table.rows:
            writer.writerow([safe_cell(cell) for cell in row])

    if report.assumptions:
        writer.writerow([])
        writer.writerow(["Calculation assumptions"])
        for assumption in report.assumptions:
            writer.writerow([safe_cell(assumption)])

    return (BOM + buffer.getvalue()).encode("utf-8")
