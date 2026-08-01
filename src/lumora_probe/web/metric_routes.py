# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""JSON metrics and alert endpoints."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from fastapi import APIRouter


class MetricsProvider(Protocol):
    """Read-side contract for event-derived metrics."""

    def snapshot_dict(self) -> Mapping[str, Any]: ...

    def plugin_snapshot(self) -> Mapping[str, Any]: ...


class AlertProvider(Protocol):
    """Read-side contract for in-process alert facts."""

    def as_dict(self) -> Mapping[str, Any]: ...


class EmptyMetricsProvider:
    """Safe empty provider for test composition and the unconfigured ASGI app."""

    def snapshot_dict(self) -> Mapping[str, Any]:
        return {"items": []}

    def plugin_snapshot(self) -> Mapping[str, Any]:
        return {"items": []}


class EmptyAlertProvider:
    def as_dict(self) -> Mapping[str, Any]:
        return {"items": []}


def create_metric_router(
    metrics_provider: MetricsProvider | None = None,
    alert_provider: AlertProvider | None = None,
) -> APIRouter:
    """Create JSON-only metrics routes; Prometheus exposition is intentionally absent."""

    metrics = metrics_provider or EmptyMetricsProvider()
    alerts = alert_provider or EmptyAlertProvider()
    router = APIRouter(prefix="/metrics", tags=["metrics"])

    @router.get("")
    def list_metrics() -> Mapping[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return metrics.snapshot_dict()

    @router.get("/plugins")
    def list_plugin_metrics() -> Mapping[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return metrics.plugin_snapshot()

    @router.get("/alerts")
    def list_alerts() -> Mapping[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return alerts.as_dict()

    return router


__all__ = [
    "AlertProvider",
    "EmptyAlertProvider",
    "EmptyMetricsProvider",
    "MetricsProvider",
    "create_metric_router",
]
