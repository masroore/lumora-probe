# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Server-rendered operational metrics dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .metric_routes import AlertProvider, EmptyAlertProvider, EmptyMetricsProvider, MetricsProvider

TEMPLATE_ROOT = Path(__file__).with_name("templates")


def create_dashboard_router(
    metrics_provider: MetricsProvider | None = None,
    alert_provider: AlertProvider | None = None,
    *,
    template_root: Path | None = None,
) -> APIRouter:
    metrics = metrics_provider or EmptyMetricsProvider()
    alerts = alert_provider or EmptyAlertProvider()
    environment = Environment(
        loader=FileSystemLoader(str(template_root or TEMPLATE_ROOT)),
        autoescape=select_autoescape(("html", "xml")),
    )
    router = APIRouter(tags=["dashboard"])

    @router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    def dashboard(request: Request) -> HTMLResponse:  # pyright: ignore[reportUnusedFunction]
        template = environment.get_template("metrics_dashboard.html")
        return HTMLResponse(
            template.render(
                request=request,
                metrics=metrics.snapshot_dict().get("items", []),
                alerts=alerts.as_dict().get("items", []),
            )
        )

    return router


__all__ = ["create_dashboard_router"]
