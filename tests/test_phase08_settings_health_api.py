# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Tests for Phase 08 settings and health resources."""

from __future__ import annotations

import httpx
import pytest

from lumora_probe.web.api import create_app
from lumora_probe.web.health_routes import InMemoryHealthProvider
from lumora_probe.web.settings_routes import InMemorySettingsProvider


@pytest.mark.asyncio
async def test_settings_expose_source_and_locked_fields() -> None:
    settings = InMemorySettingsProvider(
        {"port": {"name": "port", "value": 8000, "source": "env", "locked": True}}
    )
    application = create_app(settings_provider=settings)
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/api/v1/settings")
        update = await client.patch("/api/v1/settings", json={"port": 9000})

    assert response.status_code == 200
    assert response.json()["items"][0]["source"] == "env"
    assert update.status_code == 409
    assert update.json()["code"] == "LUMORA-SETTINGS-LOCKED-001"


@pytest.mark.asyncio
async def test_readiness_and_liveness_are_distinct() -> None:
    application = create_app(health_provider=InMemoryHealthProvider(ready=False, alive=True))
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        ready = await client.get("/api/v1/health/ready")
        live = await client.get("/api/v1/health/live")

    assert ready.status_code == 503
    assert live.status_code == 200
