"""Composition adapter joining live ring-buffer records to study browser retention."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True, slots=True)
class _RingBufferConfig:
    """Minimal config shape needed by the retention adapter."""

    retention_seconds: float


@dataclass(frozen=True, slots=True)
class _RingBufferRecord:
    """Minimal record shape needed by the retention adapter."""

    kind: str
    raw: bytes
    occurred_at: datetime
    recorded_at: datetime
    aggregate_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class RingBufferRetentionMap:
    """Build digest-keyed InstanceRetention from live ring-buffer object records."""

    def __init__(self, ring_buffer: Any, clock: Any) -> None:
        self._ring_buffer = ring_buffer
        self._clock = clock

    def retention_by_digest(self) -> dict[str, Any]:
        """Return a fresh digest-keyed retention map; never cache the result."""
        from lumora_probe.studies.contracts import InstanceRetention

        records = self._ring_buffer.snapshot()
        object_records = [r for r in records if r.kind == "object"]
        if not object_records:
            return {}
        # Group by aggregate_id for promotion window computation
        by_aggregate: dict[str | None, list] = {}
        for record in object_records:
            by_aggregate.setdefault(record.aggregate_id, []).append(record)
        result: dict[str, InstanceRetention] = {}
        for record in object_records:
            digest = hashlib.sha256(record.raw).hexdigest()
            expires_at = record.recorded_at + timedelta(
                seconds=self._ring_buffer.config.retention_seconds
            )
            group = by_aggregate.get(record.aggregate_id, [record])
            promotion_start = min(r.occurred_at for r in group)
            promotion_end = max(r.occurred_at for r in group)
            if record.aggregate_id is None:
                promotion_start = record.occurred_at
                promotion_end = record.occurred_at
            retention = InstanceRetention(
                source="ring-buffer",
                expires_at=expires_at,
                promotion_start=promotion_start,
                promotion_end=promotion_end,
                aggregate_id=record.aggregate_id,
            )
            existing = result.get(digest)
            if existing is None or (
                retention.expires_at is not None
                and (existing.expires_at is None or retention.expires_at > existing.expires_at)
            ):
                result[digest] = retention
        return result


__all__: tuple[str, ...] = ()
