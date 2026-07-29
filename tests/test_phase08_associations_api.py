"""Tests for the Phase 08 association-pair resource."""

from __future__ import annotations

import httpx
import pytest

from lumora_probe.web.api import create_app
from lumora_probe.web.resources import InMemoryResourceStore


@pytest.mark.asyncio
async def test_associations_preserve_pair_and_per_leg_timing_data() -> None:
    store = InMemoryResourceStore(
        {
            "associations": {
                "a1": {
                    "association_id": "a1",
                    "status": "completed",
                    "legs": {
                        "downstream": {"connect_ms": 2.5, "transfer_ms": 10.0},
                        "upstream": {"connect_ms": 3.5, "transfer_ms": 12.0},
                    },
                }
            }
        }
    )
    application = create_app(association_store=store)
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/associations/a1")

    assert response.status_code == 200
    assert response.json()["legs"]["downstream"]["transfer_ms"] == 10.0
    assert response.json()["legs"]["upstream"]["transfer_ms"] == 12.0
