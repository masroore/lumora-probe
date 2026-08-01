# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Phase 09 live stream and coalescing acceptance tests."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from lumora_probe.core.bus import EventBus
from lumora_probe.shared.events import EventEnvelope, EventOrigin
from lumora_probe.web.api import create_app
from lumora_probe.web.live import CoalescingGovernor, LiveSettings

IDS = tuple(f"018f0d4e-7b6a-7000-8000-00000000000{index}" for index in range(1, 10))


def make_event(index: int, *, name: str = "CStoreReceived") -> EventEnvelope:
    return EventEnvelope(
        event_id=IDS[index % len(IDS)],
        event_name=name,
        event_version=1,
        occurred_at=datetime(2026, 7, 29, 12, 0, tzinfo=UTC),
        correlation_id=IDS[(index + 1) % len(IDS)],
        aggregate_type="Capture",
        aggregate_id="capture-1",
        producer="test",
        payload={"index": index},
        origin=EventOrigin.OBSERVED,
        monotonic_ns=index + 1,
        sequence=index + 1,
    )


def publish_from_thread(application, event: EventEnvelope) -> EventEnvelope:
    future = application.state.event_bus.publish_from_thread(event)
    return future.result(timeout=2)


def test_json_stream_sends_canonical_batches_and_topic_subscriptions() -> None:
    application = create_app(event_bus=EventBus())
    with (
        TestClient(application) as client,
        client.websocket_connect(
            "/api/v1/events/stream", headers={"host": "localhost"}
        ) as websocket,
    ):
        assert websocket.receive_json()["type"] == "ready"
        websocket.send_json({"type": "subscribe", "topics": ["Capture"]})
        assert websocket.receive_json() == {
            "type": "subscribed",
            "version": 1,
            "topics": ["capture"],
            "since_sequence": None,
        }
        published = publish_from_thread(application, make_event(0))
        message = websocket.receive_json()
        assert message["type"] == "events"
        assert message["events"][0]["event_id"] == published.event_id
        assert message["events"][0]["sequence"] == 1
        websocket.close()


def test_ui_stream_requires_mounted_view_and_renders_oob_fragments() -> None:
    application = create_app(event_bus=EventBus())
    with (
        TestClient(application) as client,
        client.websocket_connect("/ws/ui", headers={"host": "localhost"}) as websocket,
    ):
        assert websocket.receive_json()["mounted"] is False
        websocket.send_json(
            {
                "type": "mount",
                "page": "live-monitor",
                "panels": ["timeline"],
                "topics": ["Capture"],
            }
        )
        assert websocket.receive_json()["panels"] == ["timeline"]
        publish_from_thread(application, make_event(0))
        message = websocket.receive_json()
        assert message["type"] == "fragments"
        assert [fragment["panel"] for fragment in message["fragments"]] == ["timeline"]
        assert 'hx-swap-oob="outerHTML"' in message["fragments"][0]["html"]
        websocket.close()


def test_hostile_websocket_origin_is_rejected() -> None:
    application = create_app(event_bus=EventBus())
    with (
        TestClient(application) as client,
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(
            "/api/v1/events/stream",
            headers={"host": "localhost", "origin": "https://evil.example"},
        ),
    ):
        pass


def test_first_paint_and_live_update_use_the_same_partial() -> None:
    application = create_app(event_bus=EventBus())
    with TestClient(application) as client:
        response = client.get(
            "/ui/partials/timeline?page=live-monitor", headers={"host": "localhost"}
        )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text.startswith('<div id="panel-timeline"')


@pytest.mark.asyncio
async def test_resume_replays_events_after_cursor() -> None:
    bus = EventBus()
    governor = CoalescingGovernor(bus=bus, settings=LiveSettings())
    await governor.start()
    for index in range(3):
        await governor.publish(make_event(index))
    client = governor.register_stream(topics=("Capture",), since_sequence=1)
    governor.enqueue_replay(client, since_sequence=1)
    message = await client.get()
    client.task_done()
    await governor.stop()
    assert [event["sequence"] for event in message["events"]] == [2, 3]
    assert message["replayed"] is True


@pytest.mark.asyncio
async def test_ui_backpressure_reports_dropped_source_sequences() -> None:
    bus = EventBus()
    governor = CoalescingGovernor(
        bus=bus,
        settings=LiveSettings(ui_queue_size=1),
    )
    client = governor.register_ui(page="live-monitor", panels=("timeline",), topics=("Capture",))
    await governor.publish(make_event(0))
    await governor.flush_now()
    await governor.publish(make_event(1))
    await governor.flush_now()
    message = await client.get()
    client.task_done()
    await governor.stop()
    assert message["dropped_count"] == 1
    assert message["dropped_sequences"] == [1]


@pytest.mark.asyncio
async def test_five_thousand_event_burst_flushes_within_ui_budget() -> None:
    bus = EventBus()
    governor = CoalescingGovernor(bus=bus, settings=LiveSettings())
    governor.register_ui(page="live-monitor", panels=("counters",), topics=("Capture",))
    for index in range(5_000):
        await governor.publish(make_event(index))
    started = time.perf_counter()
    await governor.flush_now()
    elapsed = time.perf_counter() - started
    await governor.stop()
    assert elapsed < 0.1


def test_published_asyncapi_artifact_is_fresh() -> None:
    from scripts.generate_asyncapi import render

    artifact = Path("docs/generated/asyncapi-v1.json")
    assert artifact.read_text(encoding="utf-8") == render()
    document = json.loads(artifact.read_text(encoding="utf-8"))
    assert document["channels"]["eventStream"]["address"] == "/api/v1/events/stream"
    assert document["channels"]["uiStream"]["address"] == "/ws/ui"
