# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Tests for the Phase 08 HTTP trust-boundary seams."""

from __future__ import annotations

import httpx
import pytest

from lumora_probe.web.api import create_app
from lumora_probe.web.resources import InMemoryResourceStore
from lumora_probe.web.security import SecurityPolicy


async def _client(application: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="http://localhost",
    )


@pytest.mark.asyncio
async def test_read_only_is_enforced_at_one_http_seam() -> None:
    store = InMemoryResourceStore({"captures": {"a": {"capture_id": "a"}}})
    application = create_app(
        capture_store=store,
        security_policy=SecurityPolicy(read_only=True),
    )
    async with await _client(application) as client:
        response = await client.delete("/api/v1/captures/a")

    assert response.status_code == 403
    assert response.json()["code"] == "LUMORA-WEB-READONLY-001"
    assert await store.get("captures", "a") is not None


@pytest.mark.asyncio
async def test_foreign_host_and_cross_origin_state_change_are_rejected() -> None:
    application = create_app()
    async with await _client(application) as client:
        host_response = await client.get("/api/v1", headers={"host": "evil.example"})
        origin_response = await client.patch(
            "/api/v1/settings",
            headers={"origin": "https://evil.example", "host": "localhost"},
            json={"theme": "dark"},
        )

    assert host_response.status_code == 400
    assert host_response.json()["code"] == "LUMORA-WEB-HOST-001"
    assert origin_response.status_code == 403
    assert origin_response.json()["code"] == "LUMORA-WEB-ORIGIN-001"
    assert "access-control-allow-origin" not in origin_response.headers


@pytest.mark.asyncio
async def test_forwarded_host_is_ignored_without_trusted_proxy() -> None:
    application = create_app()
    async with await _client(application) as client:
        response = await client.get(
            "/api/v1",
            headers={"host": "localhost", "x-forwarded-host": "evil.example"},
        )

    assert response.status_code == 200
