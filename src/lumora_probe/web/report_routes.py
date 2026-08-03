# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""REST routes for capture reports and background report generation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Protocol, cast

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict


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

    async def read_artifact(self, operation_id: str) -> str | None: ...


class ReportOperationProvider(Protocol):
    """Read-side operation contract used to expose report status."""

    async def get(self, operation_id: str) -> Mapping[str, Any] | None: ...


class ReportStartRequest(BaseModel):
    """JSON body for capture-scoped report generation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    format: str = "html"
    rule_set_version: str | None = None


def _report_format(operation: Mapping[str, Any]) -> str:
    parameters = operation.get("parameters")
    if isinstance(parameters, Mapping):
        values = cast(Mapping[str, Any], parameters)
        value = values.get("format")
        if isinstance(value, str) and value in {"html", "markdown", "json"}:
            return value
    return "html"


def _media_type(report_format: str) -> str:
    return {
        "html": "text/html; charset=utf-8",
        "markdown": "text/markdown; charset=utf-8",
        "json": "application/json",
    }.get(report_format, "application/octet-stream")


def _file_extension(report_format: str) -> str:
    return {"html": "html", "markdown": "md", "json": "json"}.get(report_format, "txt")


def create_reports_router(
    provider: CaptureSummaryProvider | None = None,
    job_provider: ReportJobProvider | None = None,
    operation_provider: ReportOperationProvider | None = None,
) -> APIRouter:
    """Expose report compatibility and asynchronous generation endpoints."""

    router = APIRouter(tags=["reports"])
    capture_router = APIRouter(prefix="/captures", tags=["reports"])

    @capture_router.get("/{capture_id}/report")
    async def get_capture_report(capture_id: str) -> Any:  # pyright: ignore[reportUnusedFunction]
        if provider is None:
            raise HTTPException(status_code=404, detail="Report provider is not configured")
        report = await provider.build(capture_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Capture not found")
        return report.model_dump(mode="json")

    @capture_router.post("/{capture_id}/report", status_code=202)
    async def start_capture_report(  # pyright: ignore[reportUnusedFunction]
        capture_id: str,
        request: Annotated[ReportStartRequest | None, Body()] = None,
        format: str = "html",
        rule_set_version: str | None = None,
    ) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        if job_provider is None:
            raise HTTPException(status_code=404, detail="Report job provider is not configured")
        try:
            record = await job_provider.start(
                capture_id,
                format=request.format if request is not None else format,
                rule_set_version=(
                    request.rule_set_version if request is not None else rule_set_version
                ),
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

    report_router = APIRouter(prefix="/reports", tags=["reports"])

    @report_router.get("/{operation_id}")
    async def get_report_status(  # pyright: ignore[reportUnusedFunction]
        operation_id: str,
    ) -> Mapping[str, Any]:
        if operation_provider is None:
            raise HTTPException(
                status_code=404, detail="Report operation provider is not configured"
            )
        operation = await operation_provider.get(operation_id)
        if operation is None or str(operation.get("job_type", "")) != "report-generation":
            raise HTTPException(status_code=404, detail="Report operation not found")
        parameters = operation.get("parameters")
        parameter_map = (
            dict(cast(Mapping[str, Any], parameters)) if isinstance(parameters, Mapping) else {}
        )
        artifact_available = False
        if (
            job_provider is not None
            and hasattr(job_provider, "read_artifact")
            and str(operation.get("state", "")) == "completed"
        ):
            artifact_available = (
                await job_provider.read_artifact(operation_id)  # type: ignore[attr-defined]
            ) is not None
        return {
            "operation_id": operation_id,
            "job_type": "report-generation",
            "state": operation.get("state"),
            "outcome": operation.get("outcome"),
            "progress": operation.get("progress", {}),
            "capture_id": parameter_map.get("capture_id"),
            "format": _report_format(operation),
            "rule_set_version": parameter_map.get("rule_set_version"),
            "artifact_available": artifact_available,
            "artifact_state": (
                "available"
                if artifact_available
                else "missing"
                if str(operation.get("state", "")) == "completed"
                else "pending"
            ),
            "provenance": {
                "capture_id": parameter_map.get("capture_id"),
                "rule_set_version": parameter_map.get("rule_set_version"),
                "operation_id": operation_id,
            },
        }

    @report_router.get("/{operation_id}/artifact")
    async def get_report_artifact(  # pyright: ignore[reportUnusedFunction]
        operation_id: str,
    ) -> Response:
        if job_provider is None or not hasattr(job_provider, "read_artifact"):
            raise HTTPException(
                status_code=404, detail="Report artifact provider is not configured"
            )
        if operation_provider is None:
            raise HTTPException(
                status_code=404, detail="Report operation provider is not configured"
            )
        operation = await operation_provider.get(operation_id)
        if operation is None or str(operation.get("job_type", "")) != "report-generation":
            raise HTTPException(status_code=404, detail="Report operation not found")
        if str(operation.get("state", "")) != "completed":
            raise HTTPException(status_code=409, detail="Report artifact is not available")
        body = await job_provider.read_artifact(operation_id)
        if body is None:
            raise HTTPException(status_code=410, detail="Report artifact is missing or expired")
        report_format = _report_format(operation)
        filename = f"lumora-report-{operation_id}.{_file_extension(report_format)}"
        return Response(
            content=body,
            media_type=_media_type(report_format),
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
            },
        )

    router.include_router(capture_router)
    router.include_router(report_router)
    return router


__all__: tuple[str, ...] = ()
