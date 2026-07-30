"""HTML workspace shell route with no application data dependencies."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

WorkspaceData = Mapping[str, Any]
TEMPLATE_ROOT = Path(__file__).with_name("templates")
STATIC_ROOT = Path(__file__).resolve().parents[3] / "static"

_DEFAULT_WORKSPACE: dict[str, Any] = {
    "title": "Investigation workspace",
    "subtitle": "DICOM engineering observability",
    "active_context": "No capture selected",
    "connection_state": "Ready",
    "events_dropped": 0,
    "explorer_items": (
        {"label": "Dashboard", "detail": "System overview", "active": True},
        {"label": "Live Monitor", "detail": "Associations and throughput", "active": False},
        {"label": "Captures", "detail": "Capture sessions", "active": False},
        {"label": "Studies", "detail": "Projection browser", "active": False},
        {"label": "Replay", "detail": "Replay jobs", "active": False},
    ),
    "timeline": (),
    "logs": (),
}


def _workspace_context(data: WorkspaceData | None) -> dict[str, Any]:
    """Build a stable, optional-data-only view model for the shell."""

    workspace = dict(_DEFAULT_WORKSPACE)
    if data is not None:
        workspace.update(data)
    return {"workspace": workspace}


def create_workspace_router(
    *,
    data: WorkspaceData | None = None,
    template_root: Path | None = None,
) -> APIRouter:
    """Create the root HTML route without reaching into stores or services."""

    environment = Environment(
        loader=FileSystemLoader(str(template_root or TEMPLATE_ROOT)),
        autoescape=select_autoescape(("html", "xml")),
    )
    router = APIRouter(tags=["workspace"])

    @router.get("/", response_class=HTMLResponse, include_in_schema=False)
    def workspace(request: Request) -> HTMLResponse:  # pyright: ignore[reportUnusedFunction]
        template = environment.get_template("workspace.html")
        return HTMLResponse(template.render(request=request, **_workspace_context(data)))

    return router


__all__ = ["STATIC_ROOT", "WorkspaceData", "create_workspace_router"]
