# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 24 controlled workflow contract and browser tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx
import pytest

from lumora_probe.web.api import create_app
from lumora_probe.web.replay_routes import (
    ReplayOutcome,
    ReplayPreflight,
    ReplayRequest,
)
from lumora_probe.web.settings_routes import InMemorySettingsProvider


class ReplayDouble:
    def __init__(self) -> None:
        self.created: list[ReplayRequest] = []

    async def list(self, *, limit: int, cursor: int | None = None, state: str | None = None):
        del limit, cursor, state
        return {"items": (), "next_cursor": None}

    async def get(self, operation_id: str):
        return {"operation_id": operation_id, "job_type": "event-replay", "state": "completed"}

    async def preflight(self, request: ReplayRequest) -> ReplayPreflight:
        return ReplayPreflight(outcome=ReplayOutcome.ELIGIBLE, request=request, planned_count=2)

    async def create(self, request: ReplayRequest) -> Mapping[str, Any]:
        self.created.append(request)
        return {
            "operation_id": "018f0c40-7d3d-7abc-8d2e-5b5a58fce0d0",
            "job_type": f"{request.mode.value}-replay",
            "state": "running",
        }

    async def cancel(self, operation_id: str):
        return {"operation_id": operation_id, "state": "cancellation_requested"}


class ReportDouble:
    async def start(self, capture_id: str, *, format: str = "html", rule_set_version=None):
        del capture_id, format, rule_set_version
        return type(
            "Record",
            (),
            {
                "operation_id": "report-1",
                "job_type": "report-generation",
                "state": type("State", (), {"value": "running"})(),
                "parameters": {"capture_id": "capture-1", "format": "markdown"},
            },
        )()

    async def read_artifact(self, operation_id: str) -> str | None:
        return "# Report\n" if operation_id == "report-1" else None


class OperationDouble:
    async def get(self, operation_id: str):
        if operation_id != "report-1":
            return None
        return {
            "operation_id": operation_id,
            "job_type": "report-generation",
            "state": "completed",
            "outcome": "completed",
            "progress": {"fraction": 1},
            "parameters": {
                "capture_id": "capture-1",
                "format": "markdown",
                "rule_set_version": "rules-v1",
            },
        }

    async def list(self, **kwargs):
        del kwargs
        return {"items": (), "next_cursor": None}

    async def cancel(self, operation_id: str):
        del operation_id
        return False


@pytest.mark.asyncio
async def test_replay_contracts_preflight_create_and_cancel() -> None:
    provider = ReplayDouble()
    application = create_app(replay_provider=provider)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        body = {
            "mode": "event",
            "capture_id": "capture-1",
            "fidelity": "events",
            "dry_run": True,
        }
        preflight = await client.post("/api/v1/replays/preflight", json=body)
        created = await client.post("/api/v1/replays", json=body)
        detail = await client.get("/api/v1/replays/operation-1")
        cancelled = await client.post("/api/v1/replays/operation-1/cancel")

    assert preflight.status_code == 200
    assert preflight.json()["eligible"] is True
    assert created.status_code == 202
    assert detail.status_code == 200
    assert cancelled.status_code == 200
    assert len(provider.created) == 1


@pytest.mark.asyncio
async def test_protocol_replay_requires_target_confirmation() -> None:
    application = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        response = await client.post(
            "/api/v1/replays/preflight",
            json={
                "mode": "protocol",
                "capture_id": "capture-1",
                "fidelity": "protocol",
                "dry_run": False,
                "target": {"host": "pacs.example", "port": 104},
            },
        )

    assert response.status_code == 422
    assert response.json()["code"] == "LUMORA-WEB-VALIDATION-001"


@pytest.mark.asyncio
async def test_report_status_and_artifact_use_public_reports_path() -> None:
    application = create_app(
        operation_registry=OperationDouble(),
        report_job_provider=ReportDouble(),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        status = await client.get("/api/v1/reports/report-1")
        artifact = await client.get("/api/v1/reports/report-1/artifact")
        nested = await client.get("/api/v1/captures/reports/report-1")

    assert status.status_code == 200
    assert status.json()["artifact_available"] is True
    assert status.json()["rule_set_version"] == "rules-v1"
    assert artifact.status_code == 200
    assert artifact.headers["content-type"].startswith("text/markdown")
    assert "lumora-report-report-1.md" in artifact.headers["content-disposition"]
    assert nested.status_code == 404


@pytest.mark.asyncio
async def test_settings_view_exposes_provenance_and_runtime_mutation() -> None:
    settings = InMemorySettingsProvider(
        {
            "theme": {"name": "theme", "value": "system", "source": "default"},
            "ring_buffer_seconds": {
                "name": "ring_buffer_seconds",
                "value": 1800,
                "source": "env",
            },
        }
    )
    application = create_app(settings_provider=settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        page = await client.get("/settings")
        response = await client.patch("/api/v1/settings", json={"theme": "dark"})

    assert page.status_code == 200
    assert "source: env" in page.text
    assert "Apply supported runtime settings" in page.text
    assert response.status_code == 200
    assert any(item["value"] == "dark" for item in response.json()["items"])


@pytest.mark.asyncio
async def test_plugins_page_discloses_trust_and_no_install_surface() -> None:
    application = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        response = await client.get("/plugins")
        openapi = await client.get("/openapi.json")

    assert response.status_code == 200
    assert "trusted in-process" in response.text
    assert "Installation and upload are intentionally unavailable" in response.text
    assert "/api/v1/plugins/{plugin_id}/install" not in openapi.text
