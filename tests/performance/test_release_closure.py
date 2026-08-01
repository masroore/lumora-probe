"""Structural release-closure gates for pagination, rebuild, and ring expiry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lumora_probe.captures.service import RingBufferConfig, RingBufferService, RingRecoveryError
from tests.doubles.clock import ControllableClock


@pytest.mark.component
def test_ring_eviction_writes_are_segment_bounded(tmp_path: Path) -> None:
    clock = ControllableClock(datetime(2026, 8, 1, tzinfo=UTC))
    ring = RingBufferService(
        config=RingBufferConfig(retention_seconds=3600, max_bytes=2_048),
        clock=clock,
        root=tmp_path / "ring",
    )
    for index in range(40):
        ring.record_object(
            f"object-{index}".encode(),
            study_uid=f"1.2.826.0.1.3680043.10.543.{index}.1",
            series_uid=f"1.2.826.0.1.3680043.10.543.{index}.2",
            sop_instance_uid=f"1.2.826.0.1.3680043.10.543.{index}.3",
        )
    stats = ring.persistence_stats
    assert ring.status().bytes_used <= 2_048
    assert stats["segment_count"] >= 1
    assert stats["compaction_bytes"] < stats["append_bytes"] * 2


@pytest.mark.component
@pytest.mark.parametrize("page_size", (50, 500))
def test_ring_snapshot_is_ordered_and_bounded(page_size: int) -> None:
    clock = ControllableClock(datetime(2026, 8, 1, tzinfo=UTC))
    ring = RingBufferService(config=RingBufferConfig(max_bytes=1_000_000), clock=clock)
    for index in range(page_size + 10):
        ring.record_event_raw(
            b'{"event_id":"event-%d"}' % index,
            occurred_at=clock.now(),
            monotonic_ns=index,
            aggregate_id="capture-1",
        )
        clock.advance_wall(timedelta(microseconds=1))
    page = ring.snapshot(aggregate_id="capture-1")[:page_size]
    assert len(page) == page_size
    assert [item.monotonic_ns for item in page] == list(range(page_size))


@pytest.mark.component
@pytest.mark.asyncio
async def test_ring_rotation_keeps_raw_bytes_out_of_persisted_index_and_recovers(
    tmp_path: Path,
) -> None:
    clock = ControllableClock(datetime(2026, 8, 1, tzinfo=UTC))
    ring = RingBufferService(
        config=RingBufferConfig(retention_seconds=3600, max_bytes=1_000),
        clock=clock,
        root=tmp_path / "ring",
    )
    ring._segment_target_bytes = 128  # type: ignore[attr-defined]  # deterministic turnover fixture
    for index in range(100):
        ring.record_event_raw(
            (f'{{"index":{index},"padding":"{"x" * 32}"}}').encode(),
            occurred_at=clock.now(),
            monotonic_ns=index,
        )

    assert all(record.raw is None for record in ring._records)  # type: ignore[attr-defined]
    assert ring.persistence_stats["segment_rotations"] >= 10
    expected = [record.monotonic_ns for record in ring.snapshot()]
    reloaded = RingBufferService(clock=clock, root=tmp_path / "ring")
    await reloaded.start()
    assert [record.monotonic_ns for record in reloaded.snapshot()] == expected
    assert (
        reloaded.persistence_stats["compaction_bytes"] <= reloaded.persistence_stats["append_bytes"]
    )


@pytest.mark.component
@pytest.mark.asyncio
async def test_legacy_ring_migration_is_atomic_and_preserves_records(tmp_path: Path) -> None:
    from lumora_probe.captures.service import RingBufferRecord, _ring_json

    clock = ControllableClock(datetime(2026, 8, 1, tzinfo=UTC))
    root = tmp_path / "ring"
    root.mkdir()
    record = RingBufferRecord(
        kind="event",
        raw=b'{"legacy":true}',
        occurred_at=clock.now(),
        recorded_at=clock.now(),
        monotonic_ns=7,
        metadata={"event_name": "Legacy"},
    )
    (root / "records.jsonl").write_bytes(_ring_json(record) + b"\n")

    ring = RingBufferService(clock=clock, root=root)
    await ring.start()

    assert ring.snapshot() == (record,)
    assert not (root / "records.jsonl").exists()
    assert (root / "metadata.json").is_file()
    assert tuple((root / "segments").glob("segment-*.jsonl"))


@pytest.mark.component
@pytest.mark.asyncio
async def test_ring_recovery_discards_torn_tail_cleans_temp_and_refuses_newer_format(
    tmp_path: Path,
) -> None:
    clock = ControllableClock(datetime(2026, 8, 1, tzinfo=UTC))
    root = tmp_path / "ring"
    ring = RingBufferService(clock=clock, root=root)
    ring.record_event_raw(b'{"complete":true}', occurred_at=clock.now(), monotonic_ns=1)
    segment = next((root / "segments").glob("segment-*.jsonl"))
    with segment.open("ab") as handle:
        handle.write(b'{"raw":"not-complete"')
    (root / ".metadata.json.tmp").write_text("stale", encoding="utf-8")
    (root / "segments" / ".segment-00000001.jsonl.tmp").write_text("stale", encoding="utf-8")

    recovered = RingBufferService(clock=clock, root=root)
    await recovered.start()
    assert [record.monotonic_ns for record in recovered.snapshot()] == [1]
    assert not (root / ".metadata.json.tmp").exists()
    assert not (root / "segments" / ".segment-00000001.jsonl.tmp").exists()

    (root / "metadata.json").write_text(
        '{"active_segment":0,"format_version":999,"segments":[0]}', encoding="utf-8"
    )
    newer = RingBufferService(clock=clock, root=root)
    with pytest.raises(RingRecoveryError, match="format version 999"):
        await newer.start()


@pytest.mark.component
def test_oversized_ring_record_is_retained_as_single_record(tmp_path: Path) -> None:
    clock = ControllableClock(datetime(2026, 8, 1, tzinfo=UTC))
    ring = RingBufferService(
        config=RingBufferConfig(retention_seconds=3600, max_bytes=32),
        clock=clock,
        root=tmp_path / "ring",
    )
    raw = (b'{"padding":"' + b"x" * 240 + b'"}')

    ring.record_event_raw(raw, occurred_at=clock.now(), monotonic_ns=1)

    assert ring.status().record_count == 1
    assert ring.status().bytes_used == len(raw)
    assert ring.snapshot()[0].raw == raw


@pytest.mark.component
@pytest.mark.asyncio
async def test_ring_recovers_segment_written_before_metadata_rename(tmp_path: Path) -> None:
    clock = ControllableClock(datetime(2026, 8, 1, tzinfo=UTC))
    root = tmp_path / "ring"
    ring = RingBufferService(clock=clock, root=root)
    ring._segment_target_bytes = 1  # type: ignore[attr-defined]  # force a second segment
    ring.record_event_raw(b'{"index":1}', occurred_at=clock.now(), monotonic_ns=1)
    ring.record_event_raw(b'{"index":2}', occurred_at=clock.now(), monotonic_ns=2)

    metadata = root / "metadata.json"
    value = metadata.read_text(encoding="utf-8")
    metadata.write_text(value.replace('"segments": [0, 1]', '"segments": [0]'), encoding="utf-8")

    recovered = RingBufferService(clock=clock, root=root)
    await recovered.start()

    assert [record.monotonic_ns for record in recovered.snapshot()] == [1, 2]
