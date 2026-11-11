"""PDF rendering with ReportLab (pure Python, fully offline).

Fonts: PDF's built-in fonts cover only Western European text, so user-entered names
(and currency signs) could print as boxes. On Windows we embed Segoe UI, which covers
far more; if it is unavailable we fall back to Helvetica and replace characters it
cannot show, rather than printing garbage.
"""

from __future__ import annotations

import io
from functools import cache
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from powershift.reports.model import Cell, Report, ReportTable

FONT_DIR = Path("C:/Windows/Fonts")
REGULAR_FILE, BOLD_FILE = "segoeui.ttf", "segoeuib.ttf"
UNICODE_FONT, UNICODE_BOLD = "PowerShiftSans", "PowerShiftSans-Bold"
FALLBACK_FONT, FALLBACK_BOLD = "Helvetica", "Helvetica-Bold"
MARGIN = 16 * mm
ACCENT = colors.HexColor("#0f766e")
GRID = colors.HexColor("#c9d1d9")
BAND = colors.HexColor("#f1f5f4")
MUTED = colors.HexColor("#52606d")
THOUSAND = 1000


@cache
def fonts() -> tuple[str, str, bool]:
    """(regular, bold, supports_unicode)"""
    regular, bold = FONT_DIR / REGULAR_FILE, FONT_DIR / BOLD_FILE
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont(UNICODE_FONT, str(regular)))
        pdfmetrics.registerFont(TTFont(UNICODE_BOLD, str(bold)))
        return UNICODE_FONT, UNICODE_BOLD, True
    return FALLBACK_FONT, FALLBACK_BOLD, False


def text(value: Cell, unicode_ok: bool) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        value = (
            f"{value:,.2f}" if abs(value) >= THOUSAND else f"{value:.3f}".rstrip("0").rstrip(".")
        )
    shown = str(value)
    if not unicode_ok:
        shown = shown.encode("latin-1", "replace").decode("latin-1")
    return shown


def _styles(regular: str, bold: str) -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName=regular, fontSize=9, leading=12)
    return {
        "base": base,
        "title": ParagraphStyle(
            "title", parent=base, fontName=bold, fontSize=18, leading=22, textColor=ACCENT
        ),
        "h2": ParagraphStyle(
            "h2", parent=base, fontName=bold, fontSize=11, leading=14, spaceBefore=10, spaceAfter=4
        ),
        "small": ParagraphStyle("small", parent=base, fontSize=8, leading=10, textColor=MUTED),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8, leading=10),
        "cellbold": ParagraphStyle("cellbold", parent=base, fontName=bold, fontSize=8, leading=10),
        "warn": ParagraphStyle(
            "warn",
            parent=base,
            fontName=bold,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#92400e"),
        ),
    }


MIN_COLUMN_WEIGHT = 8
MAX_COLUMN_WEIGHT = 48
MIN_COLUMN_WIDTH = 15 * mm


def _column_widths(table: ReportTable, width: float, unicode_ok: bool) -> list[float]:
    """Share the page width by how much text each column holds (clamped), so long
    text columns get room and short numeric columns stay narrow."""
    weights = []
    for index, column in enumerate(table.columns):
        cells = [len(text(row[index], unicode_ok)) for row in table.rows if index < len(row)]
        weights.append(min(max(max([len(column), *cells]), MIN_COLUMN_WEIGHT), MAX_COLUMN_WEIGHT))
    total = sum(weights)
    widths = [max(width * weight / total, MIN_COLUMN_WIDTH) for weight in weights]
    scale = width / sum(widths)  # the minimum width may have pushed the total over
    return [w * scale for w in widths]


def _table(
    table: ReportTable, styles: dict[str, ParagraphStyle], width: float, unicode_ok: bool
) -> list[Any]:
    def cell(value: Cell, strong: bool = False) -> Paragraph:
        return Paragraph(escape(text(value, unicode_ok)), styles["cellbold" if strong else "cell"])

    data = [[cell(c, strong=True) for c in table.columns]]
    for index, row in enumerate(table.rows):
        strong = table.emphasise_last_row and index == len(table.rows) - 1
        data.append([cell(c, strong=strong) for c in row])

    grid = Table(data, colWidths=_column_widths(table, width, unicode_ok), repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), BAND),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, ACCENT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if table.emphasise_last_row and table.rows:
        style.append(("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black))
    grid.setStyle(TableStyle(style))

    flow: list[Any] = []
    if table.title:
        flow.append(Paragraph(escape(text(table.title, unicode_ok)), styles["h2"]))
    flow.append(grid)
    return flow


def render_pdf(report: Report) -> bytes:
    regular, bold, unicode_ok = fonts()
    styles = _styles(regular, bold)
    buffer = io.BytesIO()
    width = A4[0] - 2 * MARGIN

    def footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont(regular, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            MARGIN, 9 * mm, text("PowerShift - estimated figures, not measurements", unicode_ok)
        )
        canvas.drawRightString(A4[0] - MARGIN, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=18 * mm,
        title=text(report.title, unicode_ok),
        author="PowerShift",
        subject="Estimated household energy report",
    )

    def p(value: str, style: str = "base") -> Paragraph:
        return Paragraph(escape(text(value, unicode_ok)), styles[style])

    def pairs(rows: list[tuple[str, str]], label_width: float) -> Table:
        return Table(
            [[p(label, "small"), p(value)] for label, value in rows],
            colWidths=[label_width, width - label_width],
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            ),
        )

    meta = [("Generated", f"{report.generated_at:%Y-%m-%d %H:%M} UTC")]
    if report.household:
        meta.append(("Household", report.household))
    if report.currency:
        meta.append(("Currency", report.currency))
    meta.extend(report.parameters)

    story: list[Any] = [p("PowerShift", "small"), p(report.title, "title"), Spacer(1, 4)]
    story += [p(report.basis, "warn"), Spacer(1, 6), pairs(meta, 32 * mm)]
    if report.tariff:
        story.append(
            KeepTogether([p("Tariff configuration", "h2"), pairs(list(report.tariff), 48 * mm)])
        )
    for table in report.tables:
        story.extend(_table(table, styles, width, unicode_ok))
    if report.assumptions:
        story.append(p("Calculation assumptions", "h2"))
        story.extend(p("- " + assumption) for assumption in report.assumptions)

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
