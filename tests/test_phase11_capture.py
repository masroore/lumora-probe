# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lumora_probe.bootstrap import _CaptureEngineAdapter
from lumora_probe.captures.format import CaptureFidelity, CapturePackage
from lumora_probe.captures.service import CaptureEngine, RingBufferConfig, RingBufferService
from lumora_probe.core.bus import EventBus
from lumora_probe.core.errors import LifecycleError
from lumora_probe.core.lifecycle import LifecycleManager
from lumora_probe.shared.events import EventEnvelope, EventOrigin
from tests.doubles.clock import ControllableClock
from tests.doubles.ids import SeededIdGenerator

CAPTURE_ID = "019f0c40-7d3d-7abc-8d2e-5b5a58fce0b5"
PROMOTED_ID = "019f0c40-7d3d-7abc-8d2e-5b5a58fce0b6"
EVENT_ID = "019f0c40-7d3d-7abc-8d2e-5b5a58fce0b7"
CORRELATION_ID = "019f0c40-7d3d-7abc-8d2e-5b5a58fce0b8"


def make_event(clock: ControllableClock, *, name: str = "AssociationStarted") -> EventEnvelope:
    return EventEnvelope(
        event_id=EVENT_ID,
        event_name=name,
        event_version=1,
        occurred_at=clock.now(),
        correlation_id=CORRELATION_ID,
        aggregate_type="Association",
        aggregate_id="assoc-1",
        producer="test",
        payload={},
        origin=EventOrigin.OBSERVED,
        monotonic_ns=clock.monotonic_ns(),
    )


@pytest.mark.asyncio
async def test_ring_buffer_enforces_bytes_and_time_retention(tmp_path: Path) -> None:
    clock = ControllableClock(datetime(2026, 7, 29, tzinfo=UTC))
    ring = RingBufferService(
        config=RingBufferConfig(retention_seconds=60, max_bytes=1000),
        clock=clock,
        root=tmp_path / "ringbuffer",
    )
    await ring.start()
    event = make_event(clock)
    ring.record_event(event)
    ring.record_pdu({"pdu": "x"}, occurred_at=clock.now(), monotonic_ns=1)
    assert ring.status().bytes_used <= 1000
    assert ring.status().record_count <= 2

    clock.advance_wall(timedelta(seconds=61))
    ring.record_event(event.model_copy(update={"occurred_at": clock.now()}))
    assert ring.snapshot(start=clock.now() - timedelta(seconds=60))
    assert ring.status().oldest_at == clock.now()
    await ring.stop()
    reloaded = RingBufferService(clock=clock, root=tmp_path / "ringbuffer")
    await reloaded.start()
    assert reloaded.status().record_count == ring.status().record_count


def test_events_only_buffer_drops_protocol_and_objects() -> None:
    clock = ControllableClock(datetime(2026, 7, 29, tzinfo=UTC))
    ring = RingBufferService(config=RingBufferConfig(events_only=True), clock=clock)
    assert ring.record_pdu({"length": 10}) is None
    assert ring.record_object(b"dicom", study_uid="1", series_uid="2", sop_instance_uid="3") is None
    assert ring.status().record_count == 0


@pytest.mark.asyncio
async def test_capture_engine_writes_explicit_session_and_promotion(tmp_path: Path) -> None:
    clock = ControllableClock(datetime(2026, 7, 29, tzinfo=UTC))
    ids = SeededIdGenerator([CAPTURE_ID, PROMOTED_ID, EVENT_ID, CORRELATION_ID])
    bus = EventBus(clock=clock, id_generator=ids)
    engine = CaptureEngine(
        tmp_path / "captures",
        event_ingress=bus,
        clock=clock,
        id_generator=ids,
    )
    await engine.start(event_bus=bus)

    capture_id = await engine.start_session(fidelity=CaptureFidelity.EVENTS)
    await bus.publish(make_event(clock), capture_id=capture_id)
    manifest = await engine.stop_session(capture_id)
    await engine.stop()

    package = CapturePackage.open(tmp_path / "captures" / capture_id)
    assert manifest.state == "completed"
    assert package.manifest.clock_anchor is not None
    assert (package.path / "events.jsonl").read_text(encoding="utf-8").count("\n") >= 2

    promoted = engine.ring_buffer
    promoted.record_event(make_event(clock, name="AssociationStarted"))
    saved = await asyncio.to_thread(
        engine.promote_window_sync,
        start=clock.now() - timedelta(seconds=1),
        end=clock.now() + timedelta(seconds=1),
        capture_id=PROMOTED_ID,
    )
    assert saved.promoted_from_buffer is True
    assert (
        CapturePackage.open(tmp_path / "captures" / PROMOTED_ID).manifest.capture_id == PROMOTED_ID
    )


@pytest.mark.asyncio
async def test_active_protocol_session_receives_pdu_and_object_sink_records(tmp_path: Path) -> None:
    clock = ControllableClock(datetime(2026, 7, 29, tzinfo=UTC))
    ids = SeededIdGenerator([CAPTURE_ID])
    engine = CaptureEngine(tmp_path / "captures", clock=clock, id_generator=ids)
    await engine.start()
    await engine.start_session(capture_id=CAPTURE_ID, fidelity=CaptureFidelity.PROTOCOL)

    engine({"association_id": "assoc-1", "pdu_type": "P_DATA_TF", "monotonic_ns": 10})
    engine.record_object(
        b"dicom-bytes",
        study_uid="1.2.3",
        series_uid="1.2.3.4",
        sop_instance_uid="1.2.3.4.5",
    )
    await engine.stop_session(CAPTURE_ID)
    await engine.stop()

    package = CapturePackage.open(tmp_path / "captures" / CAPTURE_ID)
    assert (package.path / "pdus.jsonl").read_text(encoding="utf-8").count("\n") == 1
    assert len(package.manifest.objects) == 1


@pytest.mark.asyncio
async def test_lifecycle_shutdown_marks_active_captures_interrupted_on_deadline(
    tmp_path: Path,
) -> None:
    """LifecycleManager.interrupt() seals open captures when the grace period expires."""
    clock = ControllableClock(datetime(2026, 7, 29, tzinfo=UTC))
    bus = EventBus(clock=clock)
    engine = CaptureEngine(
        tmp_path / "captures",
        event_ingress=bus,
        clock=clock,
        id_generator=SeededIdGenerator([EVENT_ID, CORRELATION_ID]),
    )
    await engine.start(event_bus=bus)
    await engine.start_session(capture_id=CAPTURE_ID, fidelity=CaptureFidelity.EVENTS)

    original_drain = engine.drain

    async def _hanging_drain() -> None:
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            # LifecycleManager cancels the timed-out drain before interrupting sessions.
            engine.drain = original_drain  # type: ignore[method-assign]
            raise

    engine.drain = _hanging_drain  # type: ignore[method-assign]
    lifecycle = LifecycleManager(shutdown_grace_seconds=0.05)
    lifecycle.register(_CaptureEngineAdapter(engine, event_bus=bus))

    try:
        await lifecycle.start()
        with pytest.raises(LifecycleError):
            await lifecycle.shutdown()

        manifest = CapturePackage.open(tmp_path / "captures" / CAPTURE_ID).manifest
        assert manifest.state == "interrupted"
        assert manifest.interruption_reason is not None
    finally:
        engine.drain = original_drain  # type: ignore[method-assign]
        await engine.stop()
        await bus.stop()
