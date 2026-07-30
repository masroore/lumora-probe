"""Tests for the ImageDisplayed client-asserted post-back (T6)."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from lumora_probe.web.api import create_app
from tests.doubles.clock import ControllableClock
from tests.doubles.ids import SeededIdGenerator

_UUID_1 = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0b5"
_UUID_2 = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0b6"
_UUID_3 = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0b7"


class Publisher:
    def __init__(self) -> None:
        self.events: list = []

    async def publish(self, event):  # type: ignore[no-untyped-def]
        self.events.append(event)
        return event


@pytest.mark.asyncio
async def test_image_displayed_post_back_is_quarantined() -> None:
    """ImageDisplayed posted via client-asserted endpoint gets CLIENT_ASSERTED origin."""
    publisher = Publisher()
    application = create_app(
        event_publisher=publisher,
        event_clock=ControllableClock(datetime(2026, 7, 30, tzinfo=UTC)),
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
                "aggregate_id": "instance-1",
                "payload": {
                    "instance_id": "instance-1",
                    "frame_number": 0,
                    "capture_id": "capture-1",
                },
            },
        )

    assert response.status_code == 200
    event = publisher.events[0]
    assert event.event_name == "ImageDisplayed"
    assert event.origin.value == "client-asserted"
    assert event.producer == "web-ui"
    assert event.payload["frame_number"] == 0


@pytest.mark.asyncio
async def test_image_displayed_payload_preserves_unknown_fields() -> None:
    """Unknown payload fields are preserved, not stripped (ADR-0006 boundary rule)."""
    publisher = Publisher()
    application = create_app(
        event_publisher=publisher,
        event_clock=ControllableClock(datetime(2026, 7, 30, tzinfo=UTC)),
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
                "aggregate_id": "instance-2",
                "payload": {
                    "instance_id": "instance-2",
                    "frame_number": 3,
                    "capture_id": "capture-2",
                    "future_field": "preserved",
                },
            },
        )

    assert response.status_code == 200
    assert publisher.events[0].payload["future_field"] == "preserved"


@pytest.mark.asyncio
async def test_image_displayed_rejects_non_viewer_category() -> None:
    """Non-Viewer category events are rejected by the client-asserted endpoint."""
    publisher = Publisher()
    application = create_app(
        event_publisher=publisher,
        event_clock=ControllableClock(datetime(2026, 7, 30, tzinfo=UTC)),
        event_id_generator=SeededIdGenerator([_UUID_1, _UUID_2]),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        response = await client.post(
            "/api/v1/events/client-asserted",
            json={
                "event_name": "CaptureStarted",
                "event_version": 1,
                "correlation_id": _UUID_3,
                "aggregate_id": "capture-1",
                "payload": {},
            },
        )

    assert response.status_code == 422
    assert len(publisher.events) == 0
