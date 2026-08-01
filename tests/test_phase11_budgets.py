# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lumora_probe.captures.service import RingBufferConfig, RingBufferService
from tests.doubles.clock import ControllableClock


@pytest.mark.component
@pytest.mark.slow
def test_representative_study_stays_within_ratified_capture_budgets() -> None:
    clock = ControllableClock(datetime(2026, 7, 29, tzinfo=UTC))
    ring = RingBufferService(
        config=RingBufferConfig(retention_seconds=1800, max_bytes=2 * 1024**3),
        clock=clock,
    )

    for instance in range(500):
        for event_number in range(10):
            ring.record_event_raw(
                f'{{"event":{event_number},"instance":{instance}}}'.encode(),
                occurred_at=clock.now(),
                monotonic_ns=instance * 10 + event_number,
                aggregate_id=f"association-{instance}",
                metadata={"event_name": "CStoreReceived"},
            )
        for pdu_number in range(32):
            ring.record_pdu(
                {"instance": instance, "pdu": pdu_number},
                occurred_at=clock.now(),
                monotonic_ns=instance * 32 + pdu_number,
                aggregate_id=f"association-{instance}",
            )

    status = ring.status()
    assert len(ring.snapshot()) == 500 * (10 + 32)
    assert status.bytes_used <= 2 * 1024**3
    assert status.oldest_at is not None
    assert status.newest_at is not None
    assert status.newest_at - status.oldest_at <= timedelta(seconds=1800)
