"""REST routes for capture summary reports."""

from __future__ import annotations

from typing import Any, Protocol

from fastapi import APIRouter, HTTPException


class CaptureSummaryProvider(Protocol):
    """Application provider for capture summary report generation."""

    async def build(self, capture_id: str) -> Any | None: ...


def create_reports_router(provider: CaptureSummaryProvider | None = None) -> APIRouter:
    """Expose capture summary reports under /captures/{capture_id}/report."""

    router = APIRouter(prefix="/captures", tags=["reports"])

    @router.get("/{capture_id}/report")
    async def get_capture_report(capture_id: str) -> Any:  # pyright: ignore[reportUnusedFunction]
        if provider is None:
            raise HTTPException(status_code=404, detail="Report provider is not configured")
        report = await provider.build(capture_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Capture not found")
        return report.model_dump(mode="json")

    return router


__all__: tuple[str, ...] = ()
