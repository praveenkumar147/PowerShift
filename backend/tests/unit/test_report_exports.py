"""CSV and PDF renderers, tested on a hand-made report so every expectation is explicit."""

from __future__ import annotations

import csv
import io
import re
from datetime import UTC, datetime

import pytest

from powershift.reports import pdf_export
from powershift.reports.csv_export import BOM, render_csv, safe_cell
from powershift.reports.model import ESTIMATE_LABEL, Report, ReportTable
from powershift.reports.pdf_export import fonts, render_pdf, text

NOW = datetime(2026, 11, 11, 9, 30, tzinfo=UTC)


def report(**changes: object) -> Report:
    base = dict(
        kind="daily_energy",
        title="Daily energy report",
        generated_at=NOW,
        household="Sharma home",
        currency="INR",
        parameters=(("Period", "2026-11-01 to 2026-11-30"),),
        tariff=(("Tariff", "Night saver"), ("Price 22:00-06:00 (every day)", "3 per kWh")),
        tables=(
            ReportTable(
                "Energy per day",
                ("Date", "Energy (kWh)", "Energy charge (INR)"),
                (("2026-11-01", 1.44, 6.96), ("Total", 1.44, 6.96)),
                True,
            ),
        ),
        assumptions=("Each weekday repeats the same routine.",),
    )
    base.update(changes)
    return Report(**base)  # type: ignore[arg-type]


def rows(content: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))


def test_csv_has_bom_metadata_tables_and_assumptions() -> None:
    content = render_csv(report())

    assert content.startswith(BOM.encode("utf-8"))
    table = rows(content)
    assert table[0] == ["PowerShift report"]
    assert ["Generated", "2026-11-11 09:30 UTC"] in table
    assert ["Household", "Sharma home"] in table
    assert ["Currency", "INR"] in table
    assert ["Basis", ESTIMATE_LABEL] in table
    assert ["Period", "2026-11-01 to 2026-11-30"] in table
    assert ["Tariff configuration"] in table
    assert ["Price 22:00-06:00 (every day)", "3 per kWh"] in table
    assert ["Energy per day"] in table
    assert ["Date", "Energy (kWh)", "Energy charge (INR)"] in table
    assert ["2026-11-01", "1.44", "6.96"] in table
    assert ["Calculation assumptions"] in table
    assert ["Each weekday repeats the same routine."] in table


def test_csv_uses_windows_line_endings_and_blank_lines_between_tables() -> None:
    text_ = render_csv(report()).decode("utf-8-sig")
    assert "\r\n" in text_ and "\r\n\r\n" in text_


def test_csv_neutralises_formula_injection_in_user_text() -> None:
    nasty = '=HYPERLINK("http://evil","x")'
    content = render_csv(
        report(
            household="+cmd",
            tables=(ReportTable("@title", ("-col",), ((nasty,), ("normal",), (-5,), (None,))),),
        )
    )
    table = rows(content)
    assert ["Household", "'+cmd"] in table
    assert ["'@title"] in table and ["'-col"] in table
    assert ["'" + nasty] in table
    assert ["normal"] in table
    assert ["-5"] in table  # real numbers are left alone
    assert [""] in table  # None becomes an empty cell


@pytest.mark.parametrize("value", ["=1+1", "+1", "-1", "@a", "\t1", "\r1"])
def test_every_formula_prefix_is_escaped(value: str) -> None:
    assert safe_cell(value) == "'" + value
    assert safe_cell("1+1") == "1+1" and safe_cell(7) == 7 and safe_cell(None) == ""


def test_csv_keeps_non_english_text() -> None:
    content = render_csv(report(household="Café ₹ घर"))
    assert ["Household", "Café ₹ घर"] in rows(content)


def test_csv_omits_empty_optional_blocks() -> None:
    table = rows(render_csv(report(household=None, currency=None, tariff=(), assumptions=())))
    labels = [row[0] for row in table if row]
    assert "Household" not in labels and "Currency" not in labels
    assert "Tariff configuration" not in labels and "Calculation assumptions" not in labels


def test_filename_stem_uses_kind_and_date() -> None:
    assert report().filename_stem == "powershift-daily-energy-20261111"


# --- PDF -------------------------------------------------------------------------------


def page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", pdf))


def test_pdf_is_a_valid_document() -> None:
    pdf = render_pdf(report())
    assert pdf.startswith(b"%PDF-") and pdf.rstrip().endswith(b"%%EOF")
    assert page_count(pdf) == 1


def test_pdf_paginates_long_tables_and_repeats_nothing_wrong() -> None:
    many = ReportTable(
        "Many rows",
        ("Date", "Value"),
        tuple((f"2026-11-{i % 28 + 1:02d}", float(i)) for i in range(250)),
    )
    assert page_count(render_pdf(report(tables=(many,)))) >= 4


def test_pdf_survives_awkward_text() -> None:
    awkward = ReportTable(
        "<b>&</b> Café ₹ घर", ("A & B", "<c>"), (("x" * 400, "line\nbreak"), (None, 3.14159))
    )
    pdf = render_pdf(report(title="Q&A <report>", household="a" * 300, tables=(awkward,)))
    assert pdf.startswith(b"%PDF-")


@pytest.mark.skipif(
    not (pdf_export.FONT_DIR / pdf_export.REGULAR_FILE).exists(), reason="Segoe UI not installed"
)
def test_pdf_embeds_a_unicode_font_when_available() -> None:
    assert fonts()[2] is True
    pdf = render_pdf(report(household="₹ Café"))
    assert b"/FontFile2" in pdf  # a TrueType font program is embedded


def test_text_formatting_and_fallback_replacement() -> None:
    assert text(None, True) == "" and text(3, True) == "3"
    assert (
        text(1234.5, True) == "1,234.50"
        and text(0.1234, True) == "0.123"
        and text(2.0, True) == "2"
    )
    assert (
        text("₹5", False) == "?5"
    )  # characters the built-in font cannot show are replaced, not garbled
    assert text("₹5", True) == "₹5"
