# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Phase 18 ring-buffer memory/eviction measurement cycles."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta

import pytest

from lumora_probe.captures.service import RingBufferConfig, RingBufferService
from tests.doubles.clock import ControllableClock


def _rss_bytes() -> int | None:
    try:
        import resource
    except ImportError:
        return None
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(usage)
    return int(usage) * 1024


@pytest.mark.component
def test_ring_buffer_eviction_cycles_respect_byte_cap() -> None:
    clock = ControllableClock(datetime(2026, 7, 31, tzinfo=UTC))
    cap = 64 * 1024
    ring = RingBufferService(
        config=RingBufferConfig(retention_seconds=1800, max_bytes=cap),
        clock=clock,
    )
    rss_samples: list[int | None] = []
    retained: list[int] = []

    for cycle in range(3):
        for index in range(200):
            payload = json.dumps(
                {"cycle": cycle, "event": index, "pad": "x" * 256},
                separators=(",", ":"),
            ).encode()
            ring.record_event_raw(
                payload,
                occurred_at=clock.now(),
                monotonic_ns=cycle * 1_000 + index,
                aggregate_id=f"association-{cycle}",
                metadata={"event_name": "CStoreReceived"},
            )
            clock.advance_wall(timedelta(milliseconds=5))
        status = ring.status()
        assert status.bytes_used <= cap
        retained.append(status.bytes_used)
        rss_samples.append(_rss_bytes())

    assert all(value <= cap for value in retained)
    print(
        {
            "dimension": "memory",
            "retained_bytes": retained,
            "rss_bytes_or_none": rss_samples,
            "cap_bytes": cap,
            "platform": sys.platform,
        }
    )
