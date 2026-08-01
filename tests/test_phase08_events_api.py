# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Tests for the Phase 08 standing event resource."""

from __future__ import annotations

import httpx
import pytest

from lumora_probe.web.api import create_app
from lumora_probe.web.resources import InMemoryResourceStore


@pytest.mark.asyncio
async def test_events_are_queryable_by_correlation_and_sequence() -> None:
    store = InMemoryResourceStore(
        {
            "events": {
                "e1": {"event_id": "e1", "correlation_id": "c1", "sequence": 1, "event_name": "A"},
                "e2": {"event_id": "e2", "correlation_id": "c1", "sequence": 2, "event_name": "B"},
                "e3": {"event_id": "e3", "correlation_id": "c2", "sequence": 1, "event_name": "C"},
            }
        }
    )
    application = create_app(event_store=store)
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/api/v1/events?correlation_id=c1&sequence=2")

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"event_id": "e2", "correlation_id": "c1", "sequence": 2, "event_name": "B"}
    ]
