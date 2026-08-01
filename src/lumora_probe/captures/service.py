"""Capture lifecycle, bounded rolling evidence, promotion, and shutdown handling."""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import json
import os
import threading
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

import pydicom

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


class CaptureClock(Protocol):
    """Injected wall and monotonic clock for capture lifecycle operations."""

    def now(self) -> datetime: ...

    def monotonic_ns(self) -> int: ...


class CaptureIdGenerator(Protocol):
    """Injected UUIDv7 identity source for capture lifecycle operations."""

    def new_id(self) -> str: ...


class CaptureEventIngress(Protocol):
    """Minimal event publication contract required by the capture engine."""

    async def publish(
        self, event: EventEnvelope, *, capture_id: str | None = None
    ) -> EventEnvelope: ...

    def publish_from_thread(
        self, event: EventEnvelope, *, capture_id: str | None = None
    ) -> concurrent.futures.Future[EventEnvelope]: ...


class CaptureRepositorySink(Protocol):
    """Minimal asynchronous index update contract used after sealing."""

    async def index(self, package: Any, *, source_root: Path | None = None) -> Any: ...


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
        clock: CaptureClock,
        root: Path | None = None,
    ) -> None:
        self.config = config or RingBufferConfig()
        self.clock = clock
        self.root = root.expanduser().resolve() if root is not None else None
        self._records: deque[RingBufferRecord] = deque()
        self._bytes_used = 0
        self._started = False
        self._lock = threading.RLock()

    @property
    def started(self) -> bool:
        return self._started

    def update_config(
        self,
        *,
        retention_seconds: float | None = None,
        max_bytes: int | None = None,
        events_only: bool | None = None,
    ) -> None:
        """Apply retention settings without replacing the running buffer."""
        with self._lock:
            self.config = replace(
                self.config,
                retention_seconds=(
                    self.config.retention_seconds
                    if retention_seconds is None
                    else retention_seconds
                ),
                max_bytes=self.config.max_bytes if max_bytes is None else max_bytes,
                events_only=self.config.events_only if events_only is None else events_only,
            )
            removed = self._expire(self.clock.now())
            while self._records and self._bytes_used > self.config.max_bytes:
                removed_record = self._records.popleft()
                self._bytes_used -= removed_record.size
                removed = True
            if removed and self.root is not None:
                self._rewrite()

    async def start(self) -> None:
        with self._lock:
            self._load()
            if self._expire(self.clock.now()) and self.root is not None:
                self._rewrite()
        self._started = True

    async def stop(self) -> None:
        with self._lock:
            self._rewrite()
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
        raw = event.to_json_bytes()
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
        with self._lock:
            return tuple(
                record
                for record in self._records
                if (start_utc is None or record.occurred_at >= start_utc)
                and (end_utc is None or record.occurred_at <= end_utc)
                and (aggregate_id is None or record.aggregate_id == aggregate_id)
            )

    def status(self) -> RingBufferStatus:
        with self._lock:
            oldest = self._records[0].recorded_at if self._records else None
            newest = self._records[-1].recorded_at if self._records else None
            bytes_used = self._bytes_used
            record_count = len(self._records)
        expires_at = oldest + timedelta(seconds=self.config.retention_seconds) if oldest else None
        return RingBufferStatus(
            enabled=self._started,
            events_only=self.config.events_only,
            retention_seconds=self.config.retention_seconds,
            max_bytes=self.config.max_bytes,
            bytes_used=bytes_used,
            record_count=record_count,
            oldest_at=oldest,
            newest_at=newest,
            expires_at=expires_at,
        )

    def _append(self, record: RingBufferRecord) -> None:
        with self._lock:
            self._records.append(record)
            self._bytes_used += record.size
            removed = self._expire(record.recorded_at)
            while self._records and self._bytes_used > self.config.max_bytes:
                expired = self._records.popleft()
                self._bytes_used -= expired.size
                removed = True
            if self.root is not None:
                if removed:
                    self._rewrite()
                else:
                    self._append_persisted(record)

    def _expire(self, now: datetime) -> bool:
        removed = False
        cutoff = now - timedelta(seconds=self.config.retention_seconds)
        while self._records and self._records[0].recorded_at < cutoff:
            expired = self._records.popleft()
            self._bytes_used -= expired.size
            removed = True
        return removed

    @property
    def _records_path(self) -> Path | None:
        return self.root / "records.jsonl" if self.root is not None else None

    def _load(self) -> None:
        path = self._records_path
        if path is None or not path.is_file() or self._records:
            return
        for line in path.read_bytes().splitlines():
            try:
                value = json.loads(line)
                record = RingBufferRecord(
                    kind=str(value["kind"]),
                    raw=base64.b64decode(value["raw"]),
                    occurred_at=datetime.fromisoformat(value["occurred_at"]),
                    recorded_at=datetime.fromisoformat(value["recorded_at"]),
                    monotonic_ns=int(value["monotonic_ns"]),
                    aggregate_id=value.get("aggregate_id"),
                    metadata=dict(value.get("metadata", {})),
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
            self._records.append(record)
            self._bytes_used += record.size

    def _append_persisted(self, record: RingBufferRecord) -> None:
        path = self._records_path
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as handle:
            handle.write(_ring_json(record))
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _rewrite(self) -> None:
        path = self._records_path
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        with temporary.open("wb") as handle:
            for record in self._records:
                handle.write(_ring_json(record))
                handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)


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
        ring_root: Path | None = None,
        ring_buffer: RingBufferService | None = None,
        event_ingress: CaptureEventIngress | None = None,
        capture_repository: CaptureRepositorySink | None = None,
        clock: CaptureClock,
        id_generator: CaptureIdGenerator,
        fsync_policy: FsyncPolicy = FsyncPolicy.ALWAYS,
    ) -> None:
        self.captures_root = captures_root.expanduser().resolve()
        self.ring_buffer = ring_buffer or RingBufferService(clock=clock, root=ring_root)
        self.event_ingress = event_ingress
        self.capture_repository = capture_repository
        self.clock = clock
        self.id_generator = id_generator
        self.fsync_policy = FsyncPolicy(fsync_policy)
        self._subscription: Any | None = None
        self._worker: asyncio.Task[None] | None = None
        self._accepting = False
        self._sessions: dict[str, _CaptureSession] = {}
        self._session_lock = threading.RLock()
        self._persistence_failures = 0

    @property
    def sessions(self) -> tuple[str, ...]:
        return tuple(self._sessions)

    @property
    def persistence_failures(self) -> int:
        return self._persistence_failures

    async def start(self, *, event_bus: Any | None = None) -> None:
        if self._accepting:
            return
        await self.ring_buffer.start()
        self._accepting = True
        bus = event_bus or self.event_ingress
        if self.event_ingress is None and bus is not None and hasattr(bus, "publish"):
            self.event_ingress = bus
        if bus is not None and hasattr(bus, "subscribe"):
            self._subscription = await bus.subscribe(channel="capture")
            self._worker = asyncio.create_task(self._consume(), name="lumora-capture-writer")

    async def stop_accepting(self) -> None:
        self._accepting = False

    async def drain(self) -> None:
        if self._subscription is not None:
            await self._subscription.join()

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
            detail=(
                f"{len(self._sessions)} active capture session(s); "
                f"persistence_failures={self._persistence_failures}"
            ),
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
        if not self._accepting:
            raise RuntimeError("capture engine is not accepting new sessions")
        if CaptureFidelity(fidelity) is CaptureFidelity.WIRE:
            raise ValueError("wire fidelity is unavailable until raw wire capture is enabled")
        identifier = capture_id or self.id_generator.new_id()
        with self._session_lock:
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
        with self._session_lock:
            self._sessions[identifier] = _CaptureSession(capture=capture, writer=writer)
        await self._publish_lifecycle(
            "CaptureStarted",
            identifier,
            {"capture_id": identifier, "fidelity": fidelity.value, "source": source},
        )
        return identifier

    async def stop_session(self, capture_id: str) -> CaptureManifest:
        session = self._session(capture_id)
        with self._session_lock:
            session.capture.stop()
        await self._publish_lifecycle("CaptureStopped", capture_id, {"capture_id": capture_id})
        await self.drain()
        with self._session_lock:
            session.capture.complete()
        await self._publish_lifecycle("CaptureCompleted", capture_id, {"capture_id": capture_id})
        await self.drain()
        with self._session_lock:
            session.writer.update_manifest(
                session.writer.manifest.model_copy(
                    update={
                        "state": CaptureState.COMPLETED.value,
                        "client_asserted_event_count": session.client_asserted_event_count,
                    }
                )
            )
            sealed = session.writer.seal(completed_at=self.clock.now())
        with self._session_lock:
            self._sessions.pop(capture_id, None)
        await self._index_if_configured(sealed, session.writer.capture_path)
        return sealed

    async def interrupt_session(self, capture_id: str, *, reason: str) -> CaptureManifest:
        session = self._session(capture_id)
        with self._session_lock:
            session.capture.interrupt(reason)
        await self._publish_lifecycle(
            "CaptureInterrupted",
            capture_id,
            {"capture_id": capture_id, "reason": reason},
        )
        await self.drain()
        with self._session_lock:
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
        with self._session_lock:
            self._sessions.pop(capture_id, None)
        await self._index_if_configured(sealed, session.writer.capture_path)
        return sealed

    async def promote_window(
        self,
        *,
        start: datetime,
        end: datetime,
        capture_id: str | None = None,
        aggregate_id: str | None = None,
    ) -> CaptureManifest:
        manifest = await asyncio.to_thread(
            self.promote_window_sync,
            start=start,
            end=end,
            capture_id=capture_id,
            aggregate_id=aggregate_id,
        )
        await self._publish_lifecycle(
            "CapturePromoted",
            manifest.capture_id,
            {
                "capture_id": manifest.capture_id,
                "requested_start": _utc(start).isoformat(),
                "requested_end": _utc(end).isoformat(),
                "partial": manifest.partial,
            },
        )
        await self.drain()
        await self._index_if_configured(manifest, self.captures_root / manifest.capture_id)
        return manifest

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
        if pdus:
            fidelity = CaptureFidelity.PROTOCOL
        elif objects:
            fidelity = CaptureFidelity.OBJECTS
        else:
            fidelity = CaptureFidelity.EVENTS
        aggregate_ids = tuple(
            sorted({record.aggregate_id for record in events if record.aggregate_id is not None})
        )
        manifest = CaptureManifest(
            capture_id=identifier,
            created_at=self.clock.now(),
            fidelity=fidelity,
            state=CaptureState.RUNNING.value,
            source="ring-buffer",
            source_capture_id=None,
            partial=bool(incomplete),
            promoted_from_buffer=True,
            incomplete_aggregates=incomplete,
            clock_anchor=ClockAnchor(
                wall_time=records[0].occurred_at,
                monotonic_ns=records[0].monotonic_ns,
            ),
            promotion_requested_start=_utc(start),
            promotion_requested_end=_utc(end),
            promotion_actual_start=records[0].occurred_at,
            promotion_actual_end=records[-1].occurred_at,
            source_aggregate_ids=aggregate_ids,
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

    def record_pdu(
        self,
        pdu: Mapping[str, Any] | bytes,
        *,
        occurred_at: datetime | None = None,
        monotonic_ns: int = 0,
        aggregate_id: str | None = None,
    ) -> RingBufferRecord | None:
        """Adapt the association PDU sink into ring and active capture streams."""
        record = self.ring_buffer.record_pdu(
            pdu,
            occurred_at=occurred_at,
            monotonic_ns=monotonic_ns,
            aggregate_id=aggregate_id,
        )
        if record is None:
            return None
        with self._session_lock:
            for session in self._sessions.values():
                if (
                    session.capture.state is CaptureState.RUNNING
                    and session.writer.manifest.fidelity is not CaptureFidelity.EVENTS
                ):
                    session.writer.append_pdu_raw(record.raw)
        return record

    def record_object(self, data: bytes, **metadata: Any) -> RingBufferRecord | None:
        """Adapt received object bytes into ring and active capture streams."""
        record = self.ring_buffer.record_object(data, **metadata)
        if record is None:
            return None
        with self._session_lock:
            for session in self._sessions.values():
                if (
                    session.capture.state is CaptureState.RUNNING
                    and session.writer.manifest.fidelity
                    in {CaptureFidelity.OBJECTS, CaptureFidelity.PROTOCOL, CaptureFidelity.WIRE}
                ):
                    session.writer.put_object(record.raw, **dict(record.metadata))
        return record

    def __call__(self, record: Mapping[str, Any]) -> RingBufferRecord | None:
        """Act as the association layer's off-bus PDU trace sink."""
        association_id = record.get("association_id")
        return self.record_pdu(
            record,
            monotonic_ns=int(record.get("monotonic_ns", 0)),
            aggregate_id=str(association_id) if association_id is not None else None,
        )

    def store_c_store(self, event: Any) -> int:
        """Act as a C-STORE sink, retaining an encoded dataset when enabled."""
        dataset = getattr(event, "dataset", None)
        if dataset is None:
            return 0xA700
        try:
            output = BytesIO()
            pydicom.dcmwrite(output, dataset, enforce_file_format=False)
            study_uid = str(dataset.StudyInstanceUID)
            series_uid = str(dataset.SeriesInstanceUID)
            sop_instance_uid = str(dataset.SOPInstanceUID)
            transfer_syntax = getattr(
                getattr(dataset, "file_meta", None), "TransferSyntaxUID", None
            )
            self.record_object(
                output.getvalue(),
                study_uid=study_uid,
                series_uid=series_uid,
                sop_instance_uid=sop_instance_uid,
                transfer_syntax_uid=str(transfer_syntax) if transfer_syntax else None,
            )
        except (AttributeError, OSError, TypeError, ValueError):
            return 0xA700
        return 0x0000

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
        with self._session_lock:
            sessions = tuple(self._sessions.values())
            for session in sessions:
                try:
                    session.writer.append_event_raw(event.to_json_bytes())
                except (OSError, ValueError):
                    self._persistence_failures += 1
                    continue
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
            with self._session_lock:
                return self._sessions[capture_id]
        except KeyError as exc:
            raise ValueError(f"capture session not found: {capture_id}") from exc

    async def _index_if_configured(self, manifest: CaptureManifest, path: Path) -> None:
        if self.capture_repository is None:
            return
        from .format import CapturePackage

        await self.capture_repository.index(
            CapturePackage.open(path),
            source_root=self.captures_root,
        )


def _incomplete_aggregates(events: Iterable[RingBufferRecord]) -> tuple[str, ...]:
    grouped: dict[str, list[str]] = {}
    for record in events:
        if record.aggregate_id is not None and str(
            record.metadata.get("event_name", "")
        ).startswith("Association"):
            grouped.setdefault(record.aggregate_id, []).append(
                str(record.metadata.get("event_name", ""))
            )
    return tuple(
        aggregate_id
        for aggregate_id, names in grouped.items()
        if names[0] != "AssociationStarted"
        or names[-1]
        not in {
            "AssociationReleased",
            "AssociationAborted",
        }
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _ring_json(record: RingBufferRecord) -> bytes:
    return _canonical_json(
        {
            "kind": record.kind,
            "raw": base64.b64encode(record.raw).decode("ascii"),
            "occurred_at": record.occurred_at.isoformat(),
            "recorded_at": record.recorded_at.isoformat(),
            "monotonic_ns": record.monotonic_ns,
            "aggregate_id": record.aggregate_id,
            "metadata": dict(record.metadata),
        }
    ).encode("utf-8")


def _validate_raw_json(raw: bytes) -> bytes:
    if not raw or b"\n" in raw.rstrip(b"\n"):
        raise ValueError("record must contain exactly one JSON value")
    json.loads(raw)
    return raw.rstrip(b"\n")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


__all__: tuple[str, ...] = ()
