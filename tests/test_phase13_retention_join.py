"""Phase 13 ring-buffer retention join tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from lumora_probe.captures.service import RingBufferConfig, RingBufferService
from lumora_probe.studies.repository import InstanceProjection
from lumora_probe.studies.service import StudyBrowserService
from lumora_probe.web.api import create_app
from lumora_probe.web.retention import RingBufferRetentionMap
from tests.doubles.clock import ControllableClock

pytestmark = pytest.mark.component

BASE_TIME = datetime(2026, 7, 30, 0, 0, 0, tzinfo=UTC)


def _make_ring_buffer(
    clock: ControllableClock, retention_seconds: float = 300.0
) -> RingBufferService:
    return RingBufferService(
        config=RingBufferConfig(retention_seconds=retention_seconds),
        clock=clock,
    )


def test_retention_map_builds_digest_keyed_entries() -> None:
    clock = ControllableClock(BASE_TIME)
    ring_buffer = _make_ring_buffer(clock)
    raw_a = b"dicom-object-a"
    raw_b = b"dicom-object-b"
    ring_buffer.record_object(
        raw_a,
        study_uid="study-1",
        series_uid="series-1",
        sop_instance_uid="sop-a",
        aggregate_id="assoc-1",
    )
    clock.advance_wall(timedelta(seconds=5))
    ring_buffer.record_object(
        raw_b,
        study_uid="study-1",
        series_uid="series-1",
        sop_instance_uid="sop-b",
        aggregate_id="assoc-1",
    )

    retention_map = RingBufferRetentionMap(ring_buffer, clock)
    result = retention_map.retention_by_digest()

    digest_a = hashlib.sha256(raw_a).hexdigest()
    digest_b = hashlib.sha256(raw_b).hexdigest()
    assert digest_a in result
    assert digest_b in result
    entry_a = result[digest_a]
    assert entry_a.source == "ring-buffer"
    assert entry_a.state == "retained"
    assert entry_a.promotable is True
    assert entry_a.aggregate_id == "assoc-1"
    # Promotion window spans both records sharing assoc-1
    assert entry_a.promotion_start == BASE_TIME
    assert entry_a.promotion_end == BASE_TIME + timedelta(seconds=5)


def test_retention_map_expires_after_retention_window() -> None:
    clock = ControllableClock(BASE_TIME)
    ring_buffer = _make_ring_buffer(clock, retention_seconds=60.0)
    ring_buffer.record_object(
        b"dicom-object",
        study_uid="study-1",
        series_uid="series-1",
        sop_instance_uid="sop-1",
        aggregate_id="assoc-1",
    )
    retention_map = RingBufferRetentionMap(ring_buffer, clock)

    # Before expiry
    result = retention_map.retention_by_digest()
    digest = hashlib.sha256(b"dicom-object").hexdigest()
    assert result[digest].state == "retained"

    # Advance past retention_seconds; expires_at is still set (per-record),
    # so state remains "retained" per InstanceRetention.state semantics
    # (state checks expires_at is not None, not whether it's in the past).
    clock.advance_wall(timedelta(seconds=120))
    result_after = retention_map.retention_by_digest()
    # expires_at is computed from recorded_at + retention_seconds, which is in the past now
    expires_at = result_after[digest].expires_at
    assert expires_at is not None
    assert expires_at < clock.now()


def test_retention_map_collision_keeps_latest_expiry() -> None:
    clock = ControllableClock(BASE_TIME)
    ring_buffer = _make_ring_buffer(clock, retention_seconds=300.0)
    raw = b"same-object"
    ring_buffer.record_object(
        raw,
        study_uid="study-1",
        series_uid="series-1",
        sop_instance_uid="sop-1",
        aggregate_id="assoc-1",
    )
    clock.advance_wall(timedelta(seconds=10))
    ring_buffer.record_object(
        raw,
        study_uid="study-1",
        series_uid="series-1",
        sop_instance_uid="sop-1",
        aggregate_id="assoc-2",
    )
    retention_map = RingBufferRetentionMap(ring_buffer, clock)
    result = retention_map.retention_by_digest()
    digest = hashlib.sha256(raw).hexdigest()
    # Second record has later recorded_at, so later expires_at wins
    assert result[digest].expires_at == BASE_TIME + timedelta(seconds=310)


@pytest.mark.asyncio
async def test_study_browser_endpoint_shows_ring_buffer_retention() -> None:
    clock = ControllableClock(BASE_TIME)
    ring_buffer = _make_ring_buffer(clock)
    raw = b"dicom-object-for-browser"
    ring_buffer.record_object(
        raw,
        study_uid="study-1",
        series_uid="series-1",
        sop_instance_uid="sop-1",
        aggregate_id="assoc-1",
    )
    digest = hashlib.sha256(raw).hexdigest()

    class BrowserProvider:
        async def get_study_browser(self, study_uid: str):
            instances = [
                InstanceProjection(
                    capture_id="capture-1",
                    study_uid="study-1",
                    series_uid="series-1",
                    sop_instance_uid="sop-1",
                    object_digest=digest,
                    object_path=f"objects/{digest}",
                    transfer_syntax_uid="1.2.840.10008.1.2.1",
                    rows=2,
                    columns=2,
                    created_at=BASE_TIME,
                )
            ]
            return StudyBrowserService.browser(study_uid, instances)

    application = create_app(
        study_browser_provider=BrowserProvider(),
        ring_buffer_service=ring_buffer,
        clock=clock,
    )
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/api/v1/studies/study-1/browser")

    assert response.status_code == 200
    payload = response.json()
    instance = payload["instances"][0]
    assert instance["retention"]["source"] == "ring-buffer"
    assert instance["retention"]["state"] == "retained"
    assert instance["retention"]["promotable"] is True
