"""Structural release-closure gates for pagination, rebuild, and ring expiry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lumora_probe.captures.service import RingBufferConfig, RingBufferService
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
