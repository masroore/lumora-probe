"""Tests for the Phase 08 capture resource routes."""

from __future__ import annotations

import httpx
import pytest

from lumora_probe.web.api import create_app
from lumora_probe.web.capture_routes import create_capture_router
from lumora_probe.web.resources import InMemoryResourceStore


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
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
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
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.delete("/api/v1/captures/a")
        missing = await client.get("/api/v1/captures/a")

    assert response.status_code == 200
    assert response.json() == {"deleted": True, "capture_id": "a"}
    assert missing.status_code == 404


def test_capture_router_can_be_assembled_independently() -> None:
    assert create_capture_router().prefix == "/captures"
