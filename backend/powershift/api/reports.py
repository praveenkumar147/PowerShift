"""Report export endpoint. Reports are generated on demand and returned as a file download;
nothing is written to disk or sent anywhere."""

from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field

from powershift.api.deps import SessionDep
from powershift.reports.csv_export import render_csv
from powershift.reports.pdf_export import render_pdf
from powershift.services.report_service import ReportFormat, ReportKind, ReportParams, ReportService

router = APIRouter(prefix="/api/reports", tags=["reports"])

MEDIA_TYPES = {ReportFormat.CSV: "text/csv; charset=utf-8", ReportFormat.PDF: "application/pdf"}


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ReportKind
    format: ReportFormat
    params: ReportParams = Field(default_factory=ReportParams)


@router.post("/export")
def export_report(session: SessionDep, request: ExportRequest) -> Response:
    """Builds the report and returns it as an attachment (`Content-Disposition`)."""
    report = ReportService(session).build(request.type, request.params)
    content = render_csv(report) if request.format is ReportFormat.CSV else render_pdf(report)
    filename = f"{report.filename_stem}.{request.format.value}"
    return Response(
        content=content,
        media_type=MEDIA_TYPES[request.format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
