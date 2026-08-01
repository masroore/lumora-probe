# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Tests for the Phase 08 quarantined client-asserted event endpoint."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from lumora_probe.web.api import create_app
from lumora_probe.web.client_event_routes import RateLimiter
from tests.doubles.clock import ControllableClock
from tests.doubles.ids import SeededIdGenerator

_UUID_1 = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0b5"
_UUID_2 = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0b6"
_UUID_3 = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0b7"


class Publisher:
    def __init__(self) -> None:
        self.events = []

    async def publish(self, event):  # type: ignore[no-untyped-def]
        self.events.append(event)
        return event


@pytest.mark.asyncio
async def test_client_event_forces_web_ui_and_viewer_quarantine() -> None:
    publisher = Publisher()
    application = create_app(
        event_publisher=publisher,
        event_clock=ControllableClock(datetime(2026, 7, 29, tzinfo=UTC)),
        event_id_generator=SeededIdGenerator([_UUID_1, _UUID_2]),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        response = await client.post(
            "/api/v1/events/client-asserted",
            json={
                "event_name": "ImageDisplayed",
                "event_version": 1,
                "correlation_id": _UUID_3,
                "aggregate_id": "viewer-1",
                "payload": {"sop_instance_uid": "1.2.3"},
            },
        )

    assert response.status_code == 200
    assert publisher.events[0].producer == "web-ui"
    assert publisher.events[0].origin.value == "client-asserted"


@pytest.mark.asyncio
async def test_client_event_rejects_non_viewer_event_and_rate_limits() -> None:
    publisher = Publisher()
    application = create_app(
        event_publisher=publisher,
        event_clock=ControllableClock(datetime(2026, 7, 29, tzinfo=UTC)),
        event_id_generator=SeededIdGenerator([_UUID_1, _UUID_2]),
        client_event_rate_limiter=RateLimiter(limit=2),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        invalid = await client.post(
            "/api/v1/events/client-asserted",
            json={
                "event_name": "CaptureStarted",
                "event_version": 1,
                "correlation_id": _UUID_3,
                "aggregate_id": "viewer-1",
                "payload": {},
            },
        )
        valid = await client.post(
            "/api/v1/events/client-asserted",
            json={
                "event_name": "ImageDisplayed",
                "event_version": 1,
                "correlation_id": _UUID_3,
                "aggregate_id": "viewer-1",
                "payload": {},
            },
        )
        limited = await client.post(
            "/api/v1/events/client-asserted",
            json={
                "event_name": "ImageDisplayed",
                "event_version": 1,
                "correlation_id": _UUID_3,
                "aggregate_id": "viewer-1",
                "payload": {},
            },
        )

    assert invalid.status_code == 422
    assert valid.status_code == 200
    assert limited.status_code == 429
