# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 22 operational first-paint, bounded contract, and protocol tests."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from lumora_probe.core.bus import EventBus
from lumora_probe.web.api import create_app
from lumora_probe.web.operation_routes import InMemoryOperationRegistry
from lumora_probe.web.resources import InMemoryResourceStore


class Health:
    async def check(self) -> dict[str, object]:
        return {
            "ready": True,
            "alive": True,
            "services": [
                {
                    "name": "dicom-listener",
                    "ready": True,
                    "alive": True,
                    "detail": "127.0.0.1:11112",
                }
            ],
        }


class Metrics:
    def snapshot_dict(self) -> dict[str, object]:
        return {"items": [{"name": "events.total", "kind": "counter", "value": 4, "labels": {}}]}

    def plugin_snapshot(self) -> dict[str, object]:
        return {"items": []}


class Alerts:
    def as_dict(self) -> dict[str, object]:
        return {"items": [{"name": "listener", "state": "Warning", "value": 1, "threshold": 0}]}


class Audit:
    async def list(
        self,
        *,
        category: str | None = None,
        limit: int = 100,
        cursor: int | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        del category, limit, cursor, entity_type, entity_id
        return (
            {
                "audit_id": 7,
                "event_type": "ConfigurationChanged",
                "entity_type": "setting",
                "entity_id": "theme",
                "occurred_at": "2026-08-02T00:00:00+00:00",
                "payload": {"correlation_id": "corr-1"},
            },
        )


@pytest.mark.asyncio
async def test_dashboard_and_live_render_provider_backed_first_paint() -> None:
    application = create_app(
        health_provider=Health(),
        metrics_provider=Metrics(),
        alert_provider=Alerts(),
        association_store=InMemoryResourceStore(
            {"associations": {"assoc-1": {"association_id": "assoc-1", "state": "active"}}}
        ),
        workspace_data={"timeline": ({"sequence": 1, "event_name": "CStoreReceived"},)},
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        dashboard = await client.get("/dashboard")
        live = await client.get("/live")

    assert "Operational Dashboard" in dashboard.text
    assert "dicom-listener" in dashboard.text
    assert "events.total" in dashboard.text
    assert "Live Monitor" in live.text
    assert "assoc-1" in live.text
    assert "CStoreReceived" in live.text
    assert "first-paint" in live.text


@pytest.mark.asyncio
async def test_operations_are_bounded_filterable_and_cancellable() -> None:
    records = {
        "op-1": {
            "operation_id": "op-1",
            "job_type": "capture-import",
            "state": "running",
            "started_at": "2026-08-02T00:00:00+00:00",
            "cancellable": True,
        },
        "op-2": {
            "operation_id": "op-2",
            "job_type": "report",
            "state": "completed",
            "started_at": "2026-08-01T00:00:00+00:00",
        },
    }
    audit: list[dict[str, object]] = []
    application = create_app(
        operation_registry=InMemoryOperationRegistry(records),
        operation_audit_sink=audit.append,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        page = await client.get("/api/v1/operations", params={"limit": 1, "state": "running"})
        cancelled = await client.post(
            "/api/v1/operations/op-1/cancel", headers={"sec-fetch-site": "same-origin"}
        )

    assert page.status_code == 200
    assert [item["operation_id"] for item in page.json()["items"]] == ["op-1"]
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "cancelled"
    assert audit == [{"action": "cancel", "operation_id": "op-1", "job_type": "capture-import"}]


@pytest.mark.asyncio
async def test_audit_page_is_read_only_bounded_and_linkable() -> None:
    application = create_app(audit_provider=Audit())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        page = await client.get("/audit", params={"category": "ConfigurationChanged"})
        api = await client.get("/api/v1/audit", params={"category": "ConfigurationChanged"})

    assert "ConfigurationChanged" in page.text
    assert "/search?q=theme" in page.text
    assert "Apply filters" in page.text
    assert api.json()["items"][0]["audit_id"] == 7


def test_ui_socket_refuses_unknown_version_and_panel_visibly() -> None:
    application = create_app(event_bus=EventBus())
    with (
        TestClient(application) as client,
        client.websocket_connect("/ws/ui", headers={"host": "localhost"}) as websocket,
    ):
        assert websocket.receive_json()["type"] == "ready"
        websocket.send_json({"type": "mount", "version": 99, "panels": ["timeline"]})
        assert "version" in websocket.receive_json()["message"]
        websocket.send_json({"type": "mount", "version": 1, "panels": ["unknown"]})
        assert "unknown UI panels" in websocket.receive_json()["message"]
        websocket.close()
