# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Composition adapters joining live ring-buffer records to study browser retention."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol, cast

from lumora_probe.studies.contracts import InstanceRetention


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
    metadata: Mapping[str, Any] = field(default_factory=dict[str, Any])


class RetentionClock(Protocol):
    """Wall clock contract used by the web composition adapter."""

    def now(self) -> datetime: ...


class _RingBufferService(Protocol):
    """Structural protocol for the live ring-buffer surface used by this adapter."""

    @property
    def config(self) -> _RingBufferConfig: ...

    def snapshot(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        aggregate_id: str | None = None,
    ) -> tuple[_RingBufferRecord, ...]: ...


class RingBufferRetentionMap:
    """Build a fresh digest-keyed retention map from live ring-buffer records."""

    def __init__(self, ring_buffer: _RingBufferService, clock: RetentionClock) -> None:
        self._ring_buffer = ring_buffer
        self._clock = clock

    def retention_by_digest(self) -> dict[str, InstanceRetention]:
        """Return current object retention; snapshot state is never cached."""
        records = tuple(
            record for record in self._ring_buffer.snapshot() if record.kind == "object"
        )
        if not records:
            return {}

        by_aggregate: dict[str | None, list[_RingBufferRecord]] = {}
        for record in records:
            by_aggregate.setdefault(record.aggregate_id, []).append(record)

        result: dict[str, InstanceRetention] = {}
        for record in records:
            digest = hashlib.sha256(record.raw).hexdigest()
            expires_at = record.recorded_at + timedelta(
                seconds=self._ring_buffer.config.retention_seconds
            )
            if record.aggregate_id is None:
                promotion_start = record.occurred_at
                promotion_end = record.occurred_at
            else:
                aggregate_records = by_aggregate[record.aggregate_id]
                promotion_start = min(item.occurred_at for item in aggregate_records)
                promotion_end = max(item.occurred_at for item in aggregate_records)
            candidate = InstanceRetention(
                source="ring-buffer",
                expires_at=expires_at,
                promotion_start=promotion_start,
                promotion_end=promotion_end,
                aggregate_id=record.aggregate_id,
            )
            existing = result.get(digest)
            if existing is None or _expires_later(candidate, existing):
                result[digest] = candidate
        return result


def _expires_later(candidate: InstanceRetention, existing: InstanceRetention) -> bool:
    """Return whether candidate wins a digest collision by expiry time."""
    if candidate.expires_at is None:
        return False
    return existing.expires_at is None or candidate.expires_at > existing.expires_at


def join_retention(
    payload: Mapping[str, Any],
    retention_by_digest: Mapping[str, InstanceRetention],
) -> Mapping[str, Any]:
    """Overlay live retention metadata on the browser's projected instances."""
    instances = payload.get("instances")
    if not isinstance(instances, list):
        return payload

    joined_instances: list[Any] = []
    instance_values = cast(list[Any], instances)
    for raw_instance in instance_values:
        if not isinstance(raw_instance, Mapping):
            joined_instances.append(raw_instance)
            continue
        instance = cast(Mapping[str, Any], raw_instance)
        digests_value = instance.get("object_digests")
        if not isinstance(digests_value, list | tuple):
            joined_instances.append(raw_instance)
            continue
        raw_digests = cast(list[Any] | tuple[Any, ...], digests_value)
        digests = tuple(digest for digest in raw_digests if isinstance(digest, str))
        retention = next(
            (retention_by_digest[digest] for digest in digests if digest in retention_by_digest),
            None,
        )
        if retention is None:
            joined_instances.append(raw_instance)
            continue
        joined_instance: dict[str, Any] = dict(instance)
        joined_instance["retention"] = retention.as_dict()
        joined_instances.append(joined_instance)

    joined_payload = dict(payload)
    joined_payload["instances"] = joined_instances
    return joined_payload


__all__ = ("RetentionClock", "RingBufferRetentionMap", "join_retention")
