# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Tests for the Phase 08 capture resource routes."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from lumora_probe.web.api import create_app
from lumora_probe.web.capture_routes import create_capture_router
from lumora_probe.web.resources import FilesystemCaptureStore, InMemoryResourceStore


class FakeRetentionProvider:
    def status(self):
        return {"enabled": True, "record_count": 3, "expires_at": "2026-07-29T00:30:00+00:00"}


@pytest.mark.asyncio
async def test_capture_collection_is_paginated_and_retrievable() -> None:
    store = InMemoryResourceStore(
        {
            "captures": {
                "a": {"capture_id": "a", "state": "sealed", "created_at": "2026-01-01"},
                "b": {"capture_id": "b", "state": "partial", "created_at": "2026-01-02"},
            }
        }
    )
    application = create_app(capture_store=store)
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/api/v1/captures?page_size=1&sort=-capture_id")
        detail = await client.get("/api/v1/captures/a")

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"capture_id": "b", "state": "partial", "created_at": "2026-01-02"}
    ]
    assert response.json()["total"] == 2
    assert detail.status_code == 200
    assert detail.json()["capture_id"] == "a"


@pytest.mark.asyncio
async def test_capture_delete_is_explicit() -> None:
    store = InMemoryResourceStore({"captures": {"a": {"capture_id": "a"}}})
    application = create_app(capture_store=store)
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.delete("/api/v1/captures/a")
        missing = await client.get("/api/v1/captures/a")

    assert response.status_code == 200
    assert response.json() == {"deleted": True, "capture_id": "a"}
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_ring_buffer_retention_state_is_exposed() -> None:
    application = create_app(retention_provider=FakeRetentionProvider())
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/api/v1/captures/ring-buffer")

    assert response.status_code == 200
    assert response.json()["record_count"] == 3


def test_capture_router_can_be_assembled_independently() -> None:
    assert create_capture_router().prefix == "/captures"


@pytest.mark.asyncio
async def test_capture_delete_removes_capture_directory(tmp_path: Path) -> None:
    capture_path = tmp_path / "capture-a"
    capture_path.mkdir()
    (capture_path / "manifest.json").write_text("{}", encoding="utf-8")
    store = FilesystemCaptureStore(
        {"captures": {"a": {"capture_id": "a", "path": str(capture_path)}}}
    )

    assert await store.delete("captures", "a") is True
    assert not capture_path.exists()


@pytest.mark.asyncio
async def test_ring_buffer_promotion_endpoint_uses_injected_provider() -> None:
    class Provider:
        def status(self):
            return {"enabled": True}

        async def promote_window(self, *, start, end, capture_id=None, aggregate_id=None):
            class Manifest:
                def model_dump(self, *, mode):
                    return {"capture_id": capture_id or "generated", "fidelity": "objects"}

            assert start.isoformat().startswith("2026-07-30")
            assert end > start
            return Manifest()

    application = create_app(retention_provider=Provider())
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.post(
            "/api/v1/captures/ring-buffer/promote",
            json={
                "start": "2026-07-30T00:00:00+00:00",
                "end": "2026-07-30T00:01:00+00:00",
                "capture_id": "capture-1",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"capture_id": "capture-1", "fidelity": "objects"}
