# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 12 event replay acceptance tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from lumora_probe.core.bus import EventBus, SubscriberChannel
from lumora_probe.replay.service import EventReplayService
from lumora_probe.shared.errors import ReplayDomainError
from lumora_probe.shared.events import EventEnvelope, EventOrigin
from tests.doubles.ids import SeededIdGenerator

UUIDS = (
    "018f0d4e-7b6a-7000-8000-000000000001",
    "018f0d4e-7b6a-7000-8000-000000000002",
    "018f0d4e-7b6a-7000-8000-000000000003",
    "018f0d4e-7b6a-7000-8000-000000000004",
)
REPLAY_IDS = (
    "018f0d4e-7b6a-7000-8000-000000000101",
    "018f0d4e-7b6a-7000-8000-000000000102",
    "018f0d4e-7b6a-7000-8000-000000000103",
    "018f0d4e-7b6a-7000-8000-000000000104",
    "018f0d4e-7b6a-7000-8000-000000000105",
)


def make_event(
    index: int,
    *,
    monotonic_ns: int,
    wall_delta: int = 0,
    payload: dict[str, Any] | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=UUIDS[index],
        event_name="CStoreReceived",
        event_version=1,
        occurred_at=datetime(2026, 7, 29, 12, 0, tzinfo=UTC) + timedelta(seconds=wall_delta),
        correlation_id=UUIDS[0],
        aggregate_type="Capture",
        aggregate_id="capture-source",
        producer="test",
        payload=payload or {"index": index},
        origin=EventOrigin.OBSERVED,
        monotonic_ns=monotonic_ns,
        sequence=index + 1,
    )


@pytest.mark.asyncio
async def test_event_replay_republishes_persisted_order_without_mutating_payload() -> None:
    bus = EventBus()
    subscription = await bus.subscribe(channel=SubscriberChannel.CAPTURE)
    sleeps: list[float] = []

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    source = (
        make_event(0, monotonic_ns=100, payload={"dataset": "first"}),
        make_event(1, monotonic_ns=2_100, payload={"dataset": "second"}),
        make_event(2, monotonic_ns=5_100, payload={"dataset": "third"}),
    )
    result = await EventReplayService(
        bus,
        sleeper=sleeper,
        id_generator=SeededIdGenerator(REPLAY_IDS),
    ).replay(
        source,
        capture_id="replay-capture",
    )

    delivered = [subscription.get_nowait() for _ in source]
    await bus.stop()

    assert result.count == 3
    assert result.replay_id == REPLAY_IDS[0]
    assert result.correlation_id == REPLAY_IDS[1]
    assert [event.event_id for event in result.events] == list(REPLAY_IDS[2:])
    assert [event.replay_id for event in result.events] == [REPLAY_IDS[0]] * 3
    assert [event.replay_of_event_id for event in result.events] == [
        event.event_id for event in source
    ]
    assert [event.correlation_id for event in result.events] == [REPLAY_IDS[1]] * 3
    assert [event.sequence for event in delivered] == [1, 2, 3]
    assert [event.payload for event in delivered] == [event.payload for event in source]
    assert sleeps == [2e-6, 3e-6]


@pytest.mark.asyncio
async def test_event_replay_scales_monotonic_gaps_not_wall_clock_gaps() -> None:
    bus = EventBus()
    source = (
        make_event(0, monotonic_ns=10, wall_delta=0),
        make_event(1, monotonic_ns=1_010, wall_delta=-3600),
    )
    sleeps: list[float] = []

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    await EventReplayService(
        bus,
        sleeper=sleeper,
        id_generator=SeededIdGenerator(REPLAY_IDS),
    ).replay(source, speed=2.0)
    await bus.stop()

    assert sleeps == [0.5e-6]


@pytest.mark.asyncio
async def test_event_replay_rejects_non_monotonic_source_before_publishing() -> None:
    bus = EventBus()
    source = (
        make_event(0, monotonic_ns=2),
        make_event(1, monotonic_ns=1),
    )
    with pytest.raises(ReplayDomainError, match="not monotonic"):
        await EventReplayService(bus).replay(source)
    assert not bus.started


@pytest.mark.asyncio
async def test_event_replay_rejects_invalid_speed() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        await EventReplayService(EventBus()).replay((), speed=0)
