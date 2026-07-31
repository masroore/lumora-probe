"""Phase 18 combined event throughput through bus, capture subscriber, and UI governor."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from lumora_probe.core.bus import EventBus, SubscriberChannel
from lumora_probe.shared.events import EventEnvelope, EventOrigin
from lumora_probe.web.live import CoalescingGovernor, LiveSettings

IDS = tuple(f"018f0d4e-7b6a-7000-8000-00000000{index:04d}" for index in range(1, 64))


def make_event(index: int) -> EventEnvelope:
    return EventEnvelope(
        event_id=IDS[index % len(IDS)],
        event_name="CStoreReceived",
        event_version=1,
        occurred_at=datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
        correlation_id=IDS[(index + 1) % len(IDS)],
        aggregate_type="Capture",
        aggregate_id="capture-throughput",
        producer="phase18",
        payload={"index": index},
        origin=EventOrigin.OBSERVED,
        monotonic_ns=index + 1,
        sequence=index + 1,
    )


@pytest.mark.component
@pytest.mark.asyncio
async def test_five_thousand_domain_events_through_bus_and_governor() -> None:
    bus = EventBus()
    await bus.start()
    captured: list[EventEnvelope] = []

    async def capture_subscriber(event: EventEnvelope) -> None:
        captured.append(event)

    await bus.subscribe(capture_subscriber, channel=SubscriberChannel.CAPTURE)
    governor = CoalescingGovernor(bus=bus, settings=LiveSettings())
    governor.register_ui(page="live-monitor", panels=("counters",), topics=("Capture",))
    started = time.perf_counter()
    try:
        for index in range(5_000):
            published = await bus.publish(make_event(index))
            await governor.publish(published)
        await governor.flush_now()
        elapsed = time.perf_counter() - started
    finally:
        await governor.stop()
        await bus.stop()

    assert len(captured) == 5_000
    assert captured[-1].sequence == 5_000
    # Existing Phase 09 gate owns the <100 ms flush budget for a 5k burst into the governor.
    # Combined bus+capture path timing remains evidence-only under Option B.
    print({"dimension": "event_throughput", "events": 5_000, "elapsed_seconds": elapsed})
