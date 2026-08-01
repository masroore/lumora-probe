# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Phase 07 event bus acceptance tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from lumora_probe.core.bus import EventBus, SubscriberChannel
from lumora_probe.shared.events import EventEnvelope, EventOrigin

UUIDS = (
    "018f0d4e-7b6a-7000-8000-000000000001",
    "018f0d4e-7b6a-7000-8000-000000000002",
)


def make_event(
    name: str = "CStoreReceived",
    *,
    aggregate_id: str = "capture-1",
    monotonic_ns: int = 1,
    payload: dict[str, Any] | None = None,
    origin: EventOrigin = EventOrigin.OBSERVED,
    producer: str = "test",
    occurred_at: datetime | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=UUIDS[0],
        event_name=name,
        event_version=1,
        occurred_at=occurred_at or datetime(2026, 7, 29, 12, 0, tzinfo=UTC),
        correlation_id=UUIDS[1],
        aggregate_type="Capture",
        aggregate_id=aggregate_id,
        producer=producer,
        payload=payload or {"sop_count": 1},
        origin=origin,
        monotonic_ns=monotonic_ns,
    )


@pytest.mark.asyncio
async def test_async_subscriber_is_awaited_and_sequences_are_gap_free() -> None:
    bus = EventBus()
    received: list[int | None] = []

    async def subscriber(event: EventEnvelope) -> None:
        await asyncio.sleep(0)
        received.append(event.sequence)

    await bus.start()
    await bus.subscribe(subscriber)
    for index in range(10):
        await bus.publish(make_event(monotonic_ns=index + 1))
    await bus.stop()
    assert received == list(range(1, 11))


@pytest.mark.asyncio
async def test_threaded_ingress_preserves_order_for_one_capture() -> None:
    bus = EventBus(ingress_capacity=8, thread_ingress_capacity=50)
    subscription = await bus.subscribe(channel=SubscriberChannel.CAPTURE)

    async def publish_from_worker(index: int) -> None:
        event = make_event(monotonic_ns=index + 1)
        future = bus.publish_from_thread(event)
        await asyncio.to_thread(future.result)

    await asyncio.gather(*(publish_from_worker(index) for index in range(50)))
    sequences = [subscription.get_nowait().sequence for _ in range(50)]
    await bus.stop()
    assert sequences == list(range(1, 51))


@pytest.mark.asyncio
async def test_threaded_ingress_saturation_is_rejected_and_observable() -> None:
    bus = EventBus(thread_ingress_capacity=1)
    await bus.subscribe(channel=SubscriberChannel.CAPTURE)
    first = bus.publish_from_thread(make_event(monotonic_ns=1))
    with pytest.raises(RuntimeError, match="threaded ingress capacity is saturated"):
        bus.publish_from_thread(make_event(monotonic_ns=2))
    assert bus.pending_thread_submissions >= 1
    await asyncio.to_thread(first.result)
    await bus.stop()
    assert bus.pending_thread_submissions == 0


@pytest.mark.asyncio
async def test_ui_channel_drops_oldest_and_exposes_exact_gap_count() -> None:
    bus = EventBus(ui_queue_size=2)
    subscription = await bus.subscribe(channel=SubscriberChannel.UI)
    for index in range(5):
        await bus.publish(make_event(monotonic_ns=index + 1))
    delivered = [subscription.get_nowait().sequence for _ in range(2)]
    await bus.stop()
    assert delivered == [4, 5]
    assert subscription.events_dropped == 3
    assert 5 - len(delivered) == subscription.events_dropped
    assert bus.diagnostics[-1].event_name == "EventsDropped"
    assert bus.diagnostics[-1].payload["dropped_count"] == 3


@pytest.mark.asyncio
async def test_capture_channel_never_drops_under_ui_saturation() -> None:
    bus = EventBus(ui_queue_size=1)
    capture = await bus.subscribe(channel=SubscriberChannel.CAPTURE)
    await bus.subscribe(channel=SubscriberChannel.UI)
    for index in range(20):
        await bus.publish(make_event(monotonic_ns=index + 1))
    capture_sequences = [capture.get_nowait().sequence for _ in range(20)]
    await bus.stop()
    assert capture_sequences == list(range(1, 21))


@pytest.mark.asyncio
async def test_client_asserted_events_are_quarantined_to_viewer() -> None:
    bus = EventBus()
    await bus.start()
    accepted = await bus.publish(
        make_event(
            name="ImageDisplayed",
            origin=EventOrigin.CLIENT_ASSERTED,
            producer="web-ui",
        )
    )
    assert accepted.sequence == 1
    with pytest.raises(ValueError):
        await bus.publish(
            make_event(
                origin=EventOrigin.CLIENT_ASSERTED,
                producer="web-ui",
            )
        )
    await bus.stop()


@pytest.mark.asyncio
async def test_clock_anomaly_records_wall_and_monotonic_deltas() -> None:
    bus = EventBus(clock_anomaly_threshold_ns=10)
    await bus.publish(
        make_event(monotonic_ns=1, occurred_at=datetime(2026, 7, 29, 12, 0, tzinfo=UTC))
    )
    await bus.publish(
        make_event(
            monotonic_ns=2,
            occurred_at=datetime(2026, 7, 29, 12, 0, 1, tzinfo=UTC),
        )
    )
    assert bus.diagnostics
    diagnostic = bus.diagnostics[-1]
    assert diagnostic.event_name == "ClockAnomalyDetected"
    assert diagnostic.payload["wall_delta_ns"] == 1_000_000_000
    assert diagnostic.payload["monotonic_delta_ns"] == 1
    await bus.stop()
