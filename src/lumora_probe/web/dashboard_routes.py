# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Server-rendered operational first-paint view models."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .metric_routes import AlertProvider, EmptyAlertProvider, EmptyMetricsProvider, MetricsProvider
from .resources import ResourceStore

TEMPLATE_ROOT = Path(__file__).with_name("templates")


class OperationalProvider(Protocol):
    """Read-side contract shared by Dashboard and Live Monitor first paint."""

    async def snapshot(
        self,
        *,
        audit_category: str | None = None,
        audit_entity_type: str | None = None,
        audit_cursor: int | None = None,
    ) -> Mapping[str, Any]: ...


class EmptyOperationalProvider:
    """Safe empty provider for unconfigured application composition."""

    async def snapshot(
        self,
        *,
        audit_category: str | None = None,
        audit_entity_type: str | None = None,
        audit_cursor: int | None = None,
    ) -> Mapping[str, Any]:
        del audit_category, audit_entity_type, audit_cursor
        return {
            "health": {"ready": True, "alive": True, "services": []},
            "readiness": "Ready",
            "services": (),
            "metrics": (),
            "alerts": (),
            "associations": (),
            "captures": (),
            "operations": (),
            "reports": (),
            "plugins": (),
            "timeline": (),
            "logs": (),
            "events_dropped": 0,
            "audit": (),
            "audit_next_cursor": None,
        }


class RuntimeOperationalProvider:
    """Compose bounded operational facts without creating a second application store."""

    def __init__(
        self,
        *,
        health_provider: Any | None = None,
        metrics_provider: MetricsProvider | None = None,
        alert_provider: AlertProvider | None = None,
        capture_store: ResourceStore | None = None,
        association_store: ResourceStore | None = None,
        operation_registry: Any | None = None,
        plugin_provider: Any | None = None,
        audit_provider: Any | None = None,
        workspace_data: Mapping[str, Any] | None = None,
    ) -> None:
        self.health_provider = health_provider
        self.metrics_provider = metrics_provider or EmptyMetricsProvider()
        self.alert_provider = alert_provider or EmptyAlertProvider()
        self.capture_store = capture_store
        self.association_store = association_store
        self.operation_registry = operation_registry
        self.plugin_provider = plugin_provider
        self.audit_provider = audit_provider
        self.workspace_data = workspace_data or {}

    async def snapshot(
        self,
        *,
        audit_category: str | None = None,
        audit_entity_type: str | None = None,
        audit_cursor: int | None = None,
    ) -> Mapping[str, Any]:
        health: Mapping[str, Any] = cast(
            Mapping[str, Any],
            await self.health_provider.check()
            if self.health_provider is not None
            else {"ready": True, "alive": True, "services": []},
        )
        metrics = _items(self.metrics_provider.snapshot_dict())
        alerts = _items(self.alert_provider.as_dict())
        associations = (
            tuple(await self.association_store.list("associations"))
            if self.association_store is not None
            else ()
        )
        captures = (
            tuple((await self.capture_store.list("captures"))[:5])
            if self.capture_store is not None
            else ()
        )
        operations = await _operation_items(self.operation_registry)
        plugins = (
            tuple(dict(record) for record in self.plugin_provider.records())
            if self.plugin_provider is not None
            else ()
        )
        audit, audit_next_cursor = await _audit_items(
            self.audit_provider,
            category=audit_category,
            entity_type=audit_entity_type,
            cursor=audit_cursor,
        )
        supplied = self.workspace_data
        ready = bool(health.get("ready", False))
        alive = bool(health.get("alive", False))
        readiness = "Ready" if ready and alive else "Degraded" if alive else "Unavailable"
        return {
            "health": dict(health),
            "readiness": readiness,
            "services": tuple(health.get("services", ())),
            "metrics": metrics,
            "alerts": alerts,
            "associations": associations,
            "captures": _provided_or(supplied.get("recent_captures"), captures),
            "operations": _provided_or(supplied.get("recent_operations"), operations),
            "reports": tuple(supplied.get("recent_reports", ())),
            "plugins": plugins,
            "timeline": tuple(supplied.get("timeline", ())),
            "logs": tuple(supplied.get("logs", ())),
            "events_dropped": int(supplied.get("events_dropped", 0) or 0),
            "audit": audit,
            "audit_next_cursor": audit_next_cursor,
        }


def create_dashboard_router(
    metrics_provider: MetricsProvider | None = None,
    alert_provider: AlertProvider | None = None,
    *,
    template_root: Path | None = None,
) -> APIRouter:
    """Create the legacy standalone metrics page."""
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


async def _operation_items(registry: Any | None) -> tuple[Mapping[str, Any], ...]:
    if registry is None or not hasattr(registry, "list"):
        return ()
    page: object = await registry.list(limit=5)
    if not isinstance(page, Mapping):
        return ()
    values: object = cast(Mapping[str, Any], page).get("items", ())
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return ()
    sequence = cast(Sequence[Any], values)
    return tuple(cast(Mapping[str, Any], item) for item in sequence if isinstance(item, Mapping))


async def _audit_items(
    provider: Any | None,
    *,
    category: str | None,
    entity_type: str | None,
    cursor: int | None,
) -> tuple[tuple[Mapping[str, Any], ...], int | None]:
    if provider is None or not hasattr(provider, "list"):
        return (), None
    try:
        records: Sequence[Any] = await provider.list(
            category=category,
            limit=25,
            cursor=cursor,
            entity_type=entity_type,
        )
    except TypeError:
        records = await provider.list(category=category, limit=25)
    items = tuple(
        record.as_dict() if hasattr(record, "as_dict") else dict(record) for record in records
    )
    next_cursor = int(items[-1]["audit_id"]) if len(items) == 25 and items else None
    return items, next_cursor


def _items(value: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    items = value.get("items", ())
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return ()
    sequence = cast(Sequence[Any], items)
    return tuple(cast(Mapping[str, Any], item) for item in sequence if isinstance(item, Mapping))


def _provided_or(value: object, fallback: Sequence[Mapping[str, Any]]) -> tuple[Any, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(cast(Sequence[Any], value))
    return tuple(fallback)


__all__ = [
    "EmptyOperationalProvider",
    "OperationalProvider",
    "RuntimeOperationalProvider",
    "create_dashboard_router",
]
