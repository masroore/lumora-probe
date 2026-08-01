"""REST routes for capture reports and background report generation."""

from __future__ import annotations

from typing import Any, Protocol

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse


class CaptureSummaryProvider(Protocol):
    """Application provider for the synchronous capture summary compatibility route."""

    async def build(self, capture_id: str) -> Any | None: ...


class ReportJobProvider(Protocol):
    """Application provider for asynchronous HTML/Markdown/JSON report generation."""

    async def start(
        self,
        capture_id: str,
        *,
        format: str = "html",
        rule_set_version: str | None = None,
    ) -> Any: ...


def create_reports_router(
    provider: CaptureSummaryProvider | None = None,
    job_provider: ReportJobProvider | None = None,
) -> APIRouter:
    """Expose report compatibility and asynchronous generation endpoints."""

    router = APIRouter(prefix="/captures", tags=["reports"])

    @router.get("/{capture_id}/report")
    async def get_capture_report(capture_id: str) -> Any:  # pyright: ignore[reportUnusedFunction]
        if provider is None:
            raise HTTPException(status_code=404, detail="Report provider is not configured")
        report = await provider.build(capture_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Capture not found")
        return report.model_dump(mode="json")

    @router.post("/{capture_id}/report", status_code=202)
    async def start_capture_report(  # pyright: ignore[reportUnusedFunction]
        capture_id: str,
        format: str = "html",
        rule_set_version: str | None = None,
    ) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        if job_provider is None:
            raise HTTPException(status_code=404, detail="Report job provider is not configured")
        try:
            record = await job_provider.start(
                capture_id,
                format=format,
                rule_set_version=rule_set_version,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return JSONResponse(
            status_code=202,
            content={
                "operation_id": record.operation_id,
                "job_type": record.job_type,
                "state": record.state.value,
                "parameters": record.parameters,
            },
        )

    return router


__all__: tuple[str, ...] = ()
