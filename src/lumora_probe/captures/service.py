"""Capture lifecycle, bounded rolling evidence, promotion, and shutdown handling."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from lumora_probe.core.bus import EventIngress, EventSubscription, SubscriberChannel
from lumora_probe.core.clock import Clock, SystemClock
from lumora_probe.core.ids import IdGenerator, UUIDv7Generator
from lumora_probe.core.lifecycle import ServiceHealth
from lumora_probe.shared.events import EventEnvelope, EventOrigin

from .domain import Capture, CaptureState
from .format import (
    CaptureFidelity,
    CaptureManifest,
    CapturePackageWriter,
    ClockAnchor,
    FsyncPolicy,
)


@dataclass(frozen=True, slots=True)
class RingBufferConfig:
    """Capacity and privacy settings for the always-on rolling buffer."""

    retention_seconds: float = 30 * 60
    max_bytes: int = 2 * 1024 * 1024 * 1024
    events_only: bool = False

    def __post_init__(self) -> None:
        if self.retention_seconds <= 0:
            raise ValueError("retention_seconds must be positive")
        if self.max_bytes <= 0:
            raise ValueError("max_bytes must be positive")


@dataclass(frozen=True, slots=True)
class RingBufferRecord:
    """One immutable evidence record held by the rolling buffer."""

    kind: str
    raw: bytes
    occurred_at: datetime
    recorded_at: datetime
    monotonic_ns: int
    aggregate_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.raw)


@dataclass(frozen=True, slots=True)
class RingBufferStatus:
    """Retention state exposed to API and UI adapters."""

    enabled: bool
    events_only: bool
    retention_seconds: float
    max_bytes: int
    bytes_used: int
    record_count: int
    oldest_at: datetime | None
    newest_at: datetime | None
    expires_at: datetime | None

    @property
    def fill_ratio(self) -> float:
        return self.bytes_used / self.max_bytes if self.max_bytes else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "events_only": self.events_only,
            "retention_seconds": self.retention_seconds,
            "max_bytes": self.max_bytes,
            "bytes_used": self.bytes_used,
            "record_count": self.record_count,
            "oldest_at": self.oldest_at.isoformat() if self.oldest_at else None,
            "newest_at": self.newest_at.isoformat() if self.newest_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "fill_ratio": self.fill_ratio,
        }


class RingBufferService:
    """Bounded, always-on evidence buffer with deterministic retention."""

    name = "capture-ring-buffer"

    def __init__(
        self,
        *,
        config: RingBufferConfig | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.config = config or RingBufferConfig()
        self.clock = clock or SystemClock()
        self._records: deque[RingBufferRecord] = deque()
        self._bytes_used = 0
        self._started = False

    @property
    def started(self) -> bool:
        return self._started

    async def start(self) -> None:
        self._started = True
        self._expire(self.clock.now())

    async def stop(self) -> None:
        self._started = False

    async def stop_accepting(self) -> None:
        self._started = False

    async def drain(self) -> None:
        return None

    async def flush(self) -> None:
        return None

    def health(self) -> ServiceHealth:
        return ServiceHealth(
            name=self.name,
            ready=self._started,
            alive=self._started,
            detail="events-only" if self.config.events_only else "events and objects",
        )

    def record_event(self, event: EventEnvelope) -> RingBufferRecord:
        """Record a canonical event without mutating the published envelope."""
        raw = _canonical_json(event.model_dump(mode="json")).encode("utf-8")
        record = RingBufferRecord(
            kind="event",
            raw=raw,
            occurred_at=event.occurred_at,
            recorded_at=self.clock.now(),
            monotonic_ns=event.monotonic_ns,
            aggregate_id=event.aggregate_id,
            metadata={
                "event_id": event.event_id,
                "event_name": event.event_name,
                "event_version": event.event_version,
                "origin": event.origin.value,
            },
        )
        self._append(record)
        return record

    def record_event_raw(
        self,
        raw: bytes,
        *,
        occurred_at: datetime,
        monotonic_ns: int,
        aggregate_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> RingBufferRecord:
        """Record one already-serialized event for byte-preserving promotion."""
        record = RingBufferRecord(
            kind="event",
            raw=_validate_raw_json(raw),
            occurred_at=_utc(occurred_at),
            recorded_at=self.clock.now(),
            monotonic_ns=monotonic_ns,
            aggregate_id=aggregate_id,
            metadata=dict(metadata or {}),
        )
        self._append(record)
        return record

    def record_pdu(
        self,
        pdu: Mapping[str, Any] | bytes,
        *,
        occurred_at: datetime | None = None,
        monotonic_ns: int = 0,
        aggregate_id: str | None = None,
    ) -> RingBufferRecord | None:
        """Record protocol metadata unless the configured privacy mode is events-only."""
        if self.config.events_only:
            return None
        raw = pdu if isinstance(pdu, bytes) else _canonical_json(pdu).encode("utf-8")
        record = RingBufferRecord(
            kind="pdu",
            raw=_validate_raw_json(raw),
            occurred_at=_utc(occurred_at or self.clock.now()),
            recorded_at=self.clock.now(),
            monotonic_ns=monotonic_ns,
            aggregate_id=aggregate_id,
        )
        self._append(record)
        return record

    def record_object(
        self,
        data: bytes,
        *,
        study_uid: str,
        series_uid: str,
        sop_instance_uid: str,
        transfer_syntax_uid: str | None = None,
        rows: int | None = None,
        columns: int | None = None,
        occurred_at: datetime | None = None,
        aggregate_id: str | None = None,
    ) -> RingBufferRecord | None:
        """Record a DICOM object for later digest-copy promotion."""
        if self.config.events_only:
            return None
        record = RingBufferRecord(
            kind="object",
            raw=bytes(data),
            occurred_at=_utc(occurred_at or self.clock.now()),
            recorded_at=self.clock.now(),
            monotonic_ns=0,
            aggregate_id=aggregate_id,
            metadata={
                "study_uid": study_uid,
                "series_uid": series_uid,
                "sop_instance_uid": sop_instance_uid,
                "transfer_syntax_uid": transfer_syntax_uid,
                "rows": rows,
                "columns": columns,
            },
        )
        self._append(record)
        return record

    def snapshot(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        aggregate_id: str | None = None,
    ) -> tuple[RingBufferRecord, ...]:
        """Return retained records in insertion order for a promotion window."""
        start_utc = _utc(start) if start is not None else None
        end_utc = _utc(end) if end is not None else None
        return tuple(
            record
            for record in self._records
            if (start_utc is None or record.occurred_at >= start_utc)
            and (end_utc is None or record.occurred_at <= end_utc)
            and (aggregate_id is None or record.aggregate_id == aggregate_id)
        )

    def status(self) -> RingBufferStatus:
        oldest = self._records[0].recorded_at if self._records else None
        newest = self._records[-1].recorded_at if self._records else None
        expires_at = oldest + timedelta(seconds=self.config.retention_seconds) if oldest else None
        return RingBufferStatus(
            enabled=self._started,
            events_only=self.config.events_only,
            retention_seconds=self.config.retention_seconds,
            max_bytes=self.config.max_bytes,
            bytes_used=self._bytes_used,
            record_count=len(self._records),
            oldest_at=oldest,
            newest_at=newest,
            expires_at=expires_at,
        )

    def _append(self, record: RingBufferRecord) -> None:
        self._records.append(record)
        self._bytes_used += record.size
        self._expire(record.recorded_at)
        while self._records and self._bytes_used > self.config.max_bytes:
            expired = self._records.popleft()
            self._bytes_used -= expired.size

    def _expire(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self.config.retention_seconds)
        while self._records and self._records[0].recorded_at < cutoff:
            expired = self._records.popleft()
            self._bytes_used -= expired.size


@dataclass(slots=True)
class _CaptureSession:
    capture: Capture
    writer: CapturePackageWriter
    client_asserted_event_count: int = 0


class CaptureEngine:
    """Coordinates the bus capture subscriber, explicit sessions, and promotion."""

    name = "capture-engine"

    def __init__(
        self,
        captures_root: Path,
        *,
        ring_buffer: RingBufferService | None = None,
        event_ingress: EventIngress | None = None,
        clock: Clock | None = None,
        id_generator: IdGenerator | None = None,
        fsync_policy: FsyncPolicy = FsyncPolicy.ALWAYS,
    ) -> None:
        self.captures_root = captures_root.expanduser().resolve()
        self.ring_buffer = ring_buffer or RingBufferService(clock=clock)
        self.event_ingress = event_ingress
        self.clock = clock or SystemClock()
        self.id_generator = id_generator or UUIDv7Generator()
        self.fsync_policy = FsyncPolicy(fsync_policy)
        self._subscription: EventSubscription | None = None
        self._worker: asyncio.Task[None] | None = None
        self._accepting = False
        self._sessions: dict[str, _CaptureSession] = {}

    @property
    def sessions(self) -> tuple[str, ...]:
        return tuple(self._sessions)

    async def start(self, *, event_bus: Any | None = None) -> None:
        if self._accepting:
            return
        await self.ring_buffer.start()
        self._accepting = True
        bus = event_bus or self.event_ingress
        if self.event_ingress is None and bus is not None and hasattr(bus, "publish"):
            self.event_ingress = bus
        if bus is not None and hasattr(bus, "subscribe"):
            self._subscription = await bus.subscribe(channel=SubscriberChannel.CAPTURE)
            self._worker = asyncio.create_task(self._consume(), name="lumora-capture-writer")

    async def stop_accepting(self) -> None:
        self._accepting = False

    async def drain(self) -> None:
        if self._subscription is not None:
            await self._subscription._queue.join()

    async def flush(self) -> None:
        await self.drain()

    async def stop(self) -> None:
        await self.drain()
        for capture_id in tuple(self._sessions):
            await self.interrupt_session(capture_id, reason="capture engine stopped")
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None
        if self._subscription is not None:
            await self._subscription.close()
            self._subscription = None
        await self.ring_buffer.stop()
        self._accepting = False

    async def interrupt(self, reason: str = "shutdown deadline") -> None:
        for capture_id in tuple(self._sessions):
            await self.interrupt_session(capture_id, reason=reason)

    def health(self) -> ServiceHealth:
        return ServiceHealth(
            name=self.name,
            ready=self._accepting,
            alive=self._accepting,
            detail=f"{len(self._sessions)} active capture session(s)",
        )

    async def start_session(
        self,
        *,
        capture_id: str | None = None,
        fidelity: CaptureFidelity = CaptureFidelity.EVENTS,
        source: str = "live",
        partial: bool = False,
        promoted_from_buffer: bool = False,
        source_capture_id: str | None = None,
        incomplete_aggregates: Iterable[str] = (),
    ) -> str:
        identifier = capture_id or self.id_generator.new_id()
        if identifier in self._sessions:
            raise ValueError(f"capture session already exists: {identifier}")
        capture = Capture(
            identifier,
            partial=partial,
            promoted_from_buffer=promoted_from_buffer,
            incomplete_aggregates=tuple(incomplete_aggregates),
        )
        capture.start()
        manifest = CaptureManifest(
            capture_id=identifier,
            created_at=self.clock.now(),
            fidelity=fidelity,
            state=CaptureState.RUNNING.value,
            source=source,
            source_capture_id=source_capture_id,
            partial=partial,
            promoted_from_buffer=promoted_from_buffer,
            incomplete_aggregates=tuple(incomplete_aggregates),
            clock_anchor=ClockAnchor(
                wall_time=self.clock.now(), monotonic_ns=self.clock.monotonic_ns()
            ),
        )
        writer = CapturePackageWriter(
            self.captures_root,
            manifest,
            fsync_policy=self.fsync_policy,
        )
        self._sessions[identifier] = _CaptureSession(capture=capture, writer=writer)
        await self._publish_lifecycle(
            "CaptureStarted",
            identifier,
            {"capture_id": identifier, "fidelity": fidelity.value, "source": source},
        )
        return identifier

    async def stop_session(self, capture_id: str) -> CaptureManifest:
        session = self._session(capture_id)
        session.capture.stop()
        await self._publish_lifecycle("CaptureStopped", capture_id, {"capture_id": capture_id})
        await self.drain()
        session.capture.complete()
        session.writer.update_manifest(
            session.writer.manifest.model_copy(
                update={
                    "state": CaptureState.COMPLETED.value,
                    "client_asserted_event_count": session.client_asserted_event_count,
                }
            )
        )
        sealed = session.writer.seal(completed_at=self.clock.now())
        self._sessions.pop(capture_id)
        return sealed

    async def interrupt_session(self, capture_id: str, *, reason: str) -> CaptureManifest:
        session = self._session(capture_id)
        session.capture.interrupt(reason)
        await self._publish_lifecycle(
            "CaptureInterrupted",
            capture_id,
            {"capture_id": capture_id, "reason": reason},
        )
        await self.drain()
        session.writer.update_manifest(
            session.writer.manifest.model_copy(
                update={
                    "state": CaptureState.INTERRUPTED.value,
                    "client_asserted_event_count": session.client_asserted_event_count,
                    "interruption_reason": reason,
                }
            )
        )
        sealed = session.writer.seal(completed_at=self.clock.now())
        self._sessions.pop(capture_id)
        return sealed

    async def promote_window(
        self,
        *,
        start: datetime,
        end: datetime,
        capture_id: str | None = None,
        aggregate_id: str | None = None,
    ) -> CaptureManifest:
        return await asyncio.to_thread(
            self.promote_window_sync,
            start=start,
            end=end,
            capture_id=capture_id,
            aggregate_id=aggregate_id,
        )

    def promote_window_sync(
        self,
        *,
        start: datetime,
        end: datetime,
        capture_id: str | None = None,
        aggregate_id: str | None = None,
    ) -> CaptureManifest:
        records = self.ring_buffer.snapshot(start=start, end=end, aggregate_id=aggregate_id)
        if not records:
            raise ValueError("promotion window contains no retained evidence")
        identifier = capture_id or self.id_generator.new_id()
        events = tuple(record for record in records if record.kind == "event")
        pdus = tuple(record for record in records if record.kind == "pdu")
        objects = tuple(record for record in records if record.kind == "object")
        incomplete = _incomplete_aggregates(events)
        fidelity = CaptureFidelity.PROTOCOL if pdus else CaptureFidelity.EVENTS
        manifest = CaptureManifest(
            capture_id=identifier,
            created_at=self.clock.now(),
            fidelity=fidelity,
            state=CaptureState.RUNNING.value,
            source="ring-buffer",
            source_capture_id=aggregate_id,
            partial=bool(incomplete),
            promoted_from_buffer=True,
            incomplete_aggregates=incomplete,
            clock_anchor=ClockAnchor(
                wall_time=records[0].occurred_at,
                monotonic_ns=records[0].monotonic_ns,
            ),
        )
        writer = CapturePackageWriter(
            self.captures_root,
            manifest,
            fsync_policy=self.fsync_policy,
        )
        for record in events:
            writer.append_event_raw(record.raw)
        for record in pdus:
            writer.append_pdu_raw(record.raw)
        for record in objects:
            metadata = dict(record.metadata)
            writer.put_object(record.raw, **metadata)
        promoted = writer.update_manifest(
            writer.manifest.model_copy(update={"state": CaptureState.COMPLETED.value})
        )
        return writer.seal(completed_at=self.clock.now()) if promoted else writer.seal()

    async def _consume(self) -> None:
        assert self._subscription is not None
        while True:
            event = await self._subscription.get()
            try:
                await asyncio.to_thread(self._record_event, event)
            finally:
                self._subscription.task_done()

    def _record_event(self, event: EventEnvelope) -> None:
        self.ring_buffer.record_event(event)
        for session in self._sessions.values():
            session.writer.append_event_raw(
                _canonical_json(event.model_dump(mode="json")).encode("utf-8")
            )
            if event.origin is EventOrigin.CLIENT_ASSERTED:
                session.client_asserted_event_count += 1

    async def _publish_lifecycle(
        self,
        event_name: str,
        capture_id: str,
        payload: Mapping[str, Any],
    ) -> None:
        if self.event_ingress is None:
            return
        event = EventEnvelope.create(
            event_name=event_name,
            event_version=1,
            correlation_id=capture_id,
            aggregate_type="Capture",
            aggregate_id=capture_id,
            producer="capture-engine",
            payload=payload,
            origin=EventOrigin.OBSERVED,
            clock=self.clock,
            id_generator=self.id_generator,
        )
        await self.event_ingress.publish(event, capture_id=capture_id)

    def _session(self, capture_id: str) -> _CaptureSession:
        try:
            return self._sessions[capture_id]
        except KeyError as exc:
            raise ValueError(f"capture session not found: {capture_id}") from exc


def _incomplete_aggregates(events: Iterable[RingBufferRecord]) -> tuple[str, ...]:
    first_by_aggregate: dict[str, str] = {}
    for record in events:
        if record.aggregate_id is not None:
            first_by_aggregate.setdefault(
                record.aggregate_id, str(record.metadata.get("event_name", ""))
            )
    return tuple(
        aggregate_id
        for aggregate_id, first_event_name in first_by_aggregate.items()
        if first_event_name != "AssociationStarted"
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_raw_json(raw: bytes) -> bytes:
    if not raw or b"\n" in raw.rstrip(b"\n"):
        raise ValueError("record must contain exactly one JSON value")
    json.loads(raw)
    return raw.rstrip(b"\n")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


__all__ = [
    "CaptureEngine",
    "RingBufferConfig",
    "RingBufferRecord",
    "RingBufferService",
    "RingBufferStatus",
]
