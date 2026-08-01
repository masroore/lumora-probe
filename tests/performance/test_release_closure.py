# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

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
    raw = b'{"padding":"' + b"x" * 240 + b'"}'

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


@pytest.mark.component
@pytest.mark.asyncio
async def test_projection_pages_use_unique_ties_and_direct_point_lookups(tmp_path: Path) -> None:
    from lumora_probe.bootstrap import _SQLiteResourceStore
    from lumora_probe.core.config import StartupConfig
    from lumora_probe.core.paths import DataPaths
    from lumora_probe.core.storage import StorageDatabases

    paths = DataPaths.from_config(StartupConfig(data_dir=tmp_path / "data"))
    paths.initialise(network_detector=lambda _: False)
    storage = StorageDatabases.from_paths(paths, network_detector=lambda _: False)
    storage.initialise()
    timestamp = "2026-08-01T00:00:00+00:00"
    with storage.index.write_transaction() as connection:
        connection.execute(
            "INSERT INTO captures VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "capture-1",
                str(paths.captures / "capture-1"),
                str(paths.captures),
                1,
                timestamp,
                timestamp,
                "completed",
                "objects",
                0,
                0,
                None,
                "a" * 64,
                timestamp,
            ),
        )
        connection.executemany(
            "INSERT INTO instances(capture_id, study_uid, series_uid, sop_instance_uid, "
            "object_digest, object_path, object_size, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    "capture-1",
                    "study",
                    "series",
                    f"same-{index % 2}",
                    f"digest-{index}",
                    f"objects/digest-{index}",
                    index,
                    timestamp,
                )
                for index in range(6)
            ),
        )
        connection.executemany(
            "INSERT INTO event_window(capture_id, sequence, event_id, event_name, event_version, "
            "observed_at, monotonic_ns, origin, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    "capture-1",
                    index,
                    f"event-{index}",
                    "Observed",
                    1,
                    timestamp,
                    index,
                    "observed",
                    f'{{"event_id":"event-{index}","sequence":{index}}}',
                )
                for index in range(6)
            ),
        )

    store = _SQLiteResourceStore(storage)
    items, total = await store.list_page("instances", offset=2, limit=2, sort="sop_instance_uid")
    assert total == 6
    assert len(items) == 2
    assert [(item["sop_instance_uid"], item["instance_id"]) for item in items] == sorted(
        (item["sop_instance_uid"], item["instance_id"]) for item in items
    )
    assert await store.get("instances", str(items[0]["instance_id"]))
    assert await store.get("events", "event-3")

    with storage.index.connection(read_only=True) as connection:
        plan = connection.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM instances ORDER BY created_at, instance_id LIMIT 2"
        ).fetchall()
    details = " ".join(str(row[3]) for row in plan)
    assert "idx_instances_created_id" in details or "INTEGER PRIMARY KEY" in details
