# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Canonical full-page and HTMX workspace route composition."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .dashboard_routes import EmptyOperationalProvider, OperationalProvider
from .ui_actions import UI_ACTIONS
from .ui_context import build_ui_context
from .ui_navigation import UI_ROUTES, UIRoute
from .workspace_routes import workspace_context

TEMPLATE_ROOT = Path(__file__).with_name("templates")


def _actions_json() -> str:
    return json.dumps(
        [
            {
                "name": action.name,
                "label": action.label,
                "href": action.href,
                "shortcut": action.shortcut,
                "unavailable_reason": action.unavailable_reason,
            }
            for action in UI_ACTIONS
        ],
        separators=(",", ":"),
    )


def _route_endpoint(
    environment: Environment,
    route: UIRoute,
    data: Mapping[str, Any] | None,
    operational_provider: OperationalProvider,
):
    async def endpoint(request: Request) -> HTMLResponse:
        params = {name: str(value) for name, value in request.path_params.items()}
        context = build_ui_context(route, params, request.query_params.get("tab"))
        if route.name == "audit":
            operational = await operational_provider.snapshot(
                audit_category=request.query_params.get("category"),
                audit_entity_type=request.query_params.get("entity_type"),
                audit_cursor=_non_negative_int(request.query_params.get("cursor")),
            )
        else:
            operational = await operational_provider.snapshot()
        template_name = (
            "views/platform_fragment.html"
            if request.headers.get("HX-Request", "").lower() == "true"
            else "base/workspace.html"
        )
        return HTMLResponse(
            environment.get_template(template_name).render(
                request=request,
                ui=context,
                operational=operational,
                actions_json=_actions_json(),
                **workspace_context(data),
            )
        )

    endpoint.__name__ = f"ui_{route.name.replace('-', '_')}"
    return endpoint


def create_ui_router(
    *,
    data: Mapping[str, Any] | None = None,
    template_root: Path | None = None,
    operational_provider: OperationalProvider | None = None,
) -> APIRouter:
    """Create all canonical HTML routes from one registry."""

    environment = Environment(
        loader=FileSystemLoader(str(template_root or TEMPLATE_ROOT)),
        autoescape=select_autoescape(("html", "xml")),
    )
    router = APIRouter(tags=["workspace"])
    provider = operational_provider or EmptyOperationalProvider()
    for route in UI_ROUTES:
        router.add_api_route(
            route.path,
            _route_endpoint(environment, route, data, provider),
            methods=["GET"],
            response_class=HTMLResponse,
            include_in_schema=False,
            name=route.name,
        )
    return router


def _non_negative_int(value: str | None) -> int | None:
    try:
        parsed = int(value) if value is not None else None
    except ValueError:
        return None
    return parsed if parsed is not None and parsed >= 0 else None


__all__ = ["create_ui_router"]
