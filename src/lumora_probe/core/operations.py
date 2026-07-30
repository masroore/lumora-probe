"""Durable operation audit records with in-memory execution state elsewhere."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from lumora_probe.shared.events import EventEnvelope, EventOrigin

from .clock import Clock, SystemClock
from .ids import IdGenerator, UUIDv7Generator
from .storage import StorageDatabases


class JobState(StrEnum):
    """Lifecycle states for in-memory background jobs."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class CancellationToken:
    """Cooperative cancellation signal passed to a background job."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    async def wait(self) -> None:
        await self._event.wait()


@dataclass(slots=True)
class JobRecord:
    """Mutable in-memory execution snapshot for one background job."""

    operation_id: str
    job_type: str
    parameters: dict[str, Any]
    state: JobState
    started_at: datetime
    completed_at: datetime | None = None
    outcome: str | None = None
    progress: dict[str, Any] = field(default_factory=dict)
    interruption_reason: str | None = None


JobWorker = Callable[["JobContext"], Awaitable[str | None]]


class JobProgressPublisher(Protocol):
    """Minimal event-bus publisher used for job progress."""

    async def publish(
        self, event: EventEnvelope, *, capture_id: str | None = None
    ) -> EventEnvelope:
        """Publish one progress event on the loop-owned bus."""
        ...


@dataclass(slots=True)
class JobContext:
    """Execution context exposing cooperative cancellation and progress reporting."""

    operation_id: str
    cancellation: CancellationToken
    _report: Callable[[Mapping[str, Any]], Awaitable[None]]

    async def report_progress(self, progress: Mapping[str, Any]) -> None:
        await self._report(progress)


class InMemoryJobRegistry:
    """Own asyncio tasks while exposing immutable-style job snapshots."""

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        id_generator: IdGenerator | None = None,
        durable: SQLiteOperationRegistry | None = None,
        progress_publisher: JobProgressPublisher | None = None,
        concurrency_limits: Mapping[str, int] | None = None,
    ) -> None:
        self.clock = clock if clock is not None else SystemClock()
        self.id_generator = id_generator if id_generator is not None else UUIDv7Generator()
        self.durable = durable
        self.progress_publisher = progress_publisher
        self.concurrency_limits = dict(concurrency_limits or {})
        if any(type(limit) is not int or limit < 1 for limit in self.concurrency_limits.values()):
            raise ValueError("concurrency limits must be positive integers")
        self._active_by_type: dict[str, int] = {}
        self._records: dict[str, JobRecord] = {}
        self._tokens: dict[str, CancellationToken] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def start(
        self,
        job_type: str,
        worker: JobWorker,
        *,
        parameters: Mapping[str, Any] = {},
    ) -> JobRecord:
        """Start one job without blocking the caller."""
        if not job_type.strip():
            raise ValueError("job_type must be a non-empty string")
        limit = self.concurrency_limits.get(job_type)
        active = self._active_by_type.get(job_type, 0)
        if limit is not None and active >= limit:
            raise RuntimeError(f"concurrency limit reached for job type: {job_type}")
        operation_id = self.id_generator.new_id()
        record = JobRecord(
            operation_id=operation_id,
            job_type=job_type,
            parameters=dict(parameters),
            state=JobState.RUNNING,
            started_at=self.clock.now(),
        )
        token = CancellationToken()
        self._records[operation_id] = record
        self._tokens[operation_id] = token
        self._active_by_type[job_type] = active + 1
        if self.durable is not None:
            await self.durable.start(
                operation_id=operation_id,
                job_type=job_type,
                parameters=record.parameters,
                started_at=record.started_at.isoformat(),
            )
        self._tasks[operation_id] = asyncio.create_task(self._run(record, token, worker))
        snapshot = self._snapshot(record)
        assert snapshot is not None
        return snapshot

    async def get(self, operation_id: str) -> JobRecord | None:
        """Return a snapshot of one in-memory job."""
        record = self._records.get(operation_id)
        return self._snapshot(record) if record is not None else None

    async def cancel(self, operation_id: str) -> bool:
        """Request cooperative cancellation for a running job."""
        record = self._records.get(operation_id)
        token = self._tokens.get(operation_id)
        if record is None or token is None or record.state is not JobState.RUNNING:
            return False
        token.cancel()
        return True

    async def wait(self, operation_id: str) -> JobRecord | None:
        """Wait for a known job to finish and return its final snapshot."""
        task = self._tasks.get(operation_id)
        if task is not None:
            await task
        return await self.get(operation_id)

    async def startup_sweep(self, *, reason: str) -> int:
        """Mark durable and in-memory running jobs interrupted after process restart."""
        durable_count = 0
        if self.durable is not None:
            durable_count = await self.durable.mark_running_interrupted(reason=reason)
        await self.interrupt_running(reason)
        return durable_count

    async def interrupt_running(self, reason: str) -> int:
        """Mark in-memory running jobs interrupted during shutdown."""
        count = 0
        for operation_id, record in self._records.items():
            if record.state is JobState.RUNNING:
                self._tokens[operation_id].cancel()
                record.state = JobState.INTERRUPTED
                record.interruption_reason = reason
                record.completed_at = self.clock.now()
                count += 1
                if self.durable is not None:
                    await self.durable.interrupt(operation_id=operation_id, reason=reason)
        return count

    async def _run(self, record: JobRecord, token: CancellationToken, worker: JobWorker) -> None:
        context = JobContext(
            record.operation_id,
            token,
            lambda progress: self._progress(record.operation_id, progress),
        )
        try:
            outcome = await worker(context)
            if record.state is JobState.INTERRUPTED:
                return
            record.state = JobState.CANCELLED if token.is_cancelled else JobState.COMPLETED
            record.outcome = outcome
        except asyncio.CancelledError:
            record.state = JobState.INTERRUPTED
            record.interruption_reason = "job task cancelled"
            raise
        except Exception as exc:  # noqa: BLE001 - job failures are recorded, not hidden
            record.state = JobState.FAILED
            record.outcome = str(exc)
        finally:
            if record.completed_at is None:
                record.completed_at = self.clock.now()
            if self.durable is not None and record.state is not JobState.INTERRUPTED:
                await self.durable.complete(
                    record.operation_id,
                    completed_at=record.completed_at.isoformat(),
                    outcome=record.outcome or record.state.value,
                    state=record.state.value,
                )
            active = self._active_by_type.get(record.job_type, 1) - 1
            if active > 0:
                self._active_by_type[record.job_type] = active
            else:
                self._active_by_type.pop(record.job_type, None)

    async def _progress(self, operation_id: str, progress: Mapping[str, Any]) -> None:
        record = self._records[operation_id]
        record.progress = dict(progress)
        if self.durable is not None:
            await self.durable.update_progress(operation_id, progress)
        if self.progress_publisher is not None:
            event = EventEnvelope.create(
                event_name="ReplayProgressed",
                event_version=1,
                correlation_id=operation_id,
                aggregate_type="Operation",
                aggregate_id=operation_id,
                producer="job-registry",
                payload={
                    "operation_id": operation_id,
                    "job_type": record.job_type,
                    **record.progress,
                },
                origin=EventOrigin.OBSERVED,
                clock=self.clock,
                id_generator=self.id_generator,
            )
            await self.progress_publisher.publish(event)

    @staticmethod
    def _snapshot(record: JobRecord | None) -> JobRecord | None:
        if record is None:
            return None
        return replace(record, parameters=dict(record.parameters), progress=dict(record.progress))


class SQLiteOperationRegistry:
    """Persist operation history in the authoritative application database."""

    def __init__(self, databases: StorageDatabases) -> None:
        self.databases = databases

    async def get(self, operation_id: str) -> dict[str, Any] | None:
        rows = await self.databases.app.execute_read(
            "SELECT operation_id, job_type, parameters_json, state, started_at, completed_at, "
            "outcome, progress_json, interruption_reason FROM jobs WHERE operation_id = ?",
            (operation_id,),
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "operation_id": row["operation_id"],
            "job_type": row["job_type"],
            "parameters": json.loads(row["parameters_json"]),
            "state": row["state"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "outcome": row["outcome"],
            "progress": json.loads(row["progress_json"]),
            "interruption_reason": row["interruption_reason"],
        }

    async def start(
        self,
        *,
        operation_id: str,
        job_type: str,
        parameters: Mapping[str, Any],
        started_at: str,
    ) -> None:
        await self.databases.app.execute_write(
            "INSERT INTO jobs(operation_id, job_type, parameters_json, state, started_at, "
            "completed_at, outcome, progress_json, interruption_reason) "
            "VALUES (?, ?, ?, 'running', ?, NULL, NULL, '{}', NULL)",
            (operation_id, job_type, json.dumps(dict(parameters), sort_keys=True), started_at),
        )

    async def update_progress(self, operation_id: str, progress: Mapping[str, Any]) -> None:
        await self.databases.app.execute_write(
            "UPDATE jobs SET progress_json = ? WHERE operation_id = ?",
            (json.dumps(dict(progress), sort_keys=True), operation_id),
        )

    async def complete(
        self,
        operation_id: str,
        *,
        completed_at: str,
        outcome: str,
        state: str = "completed",
    ) -> None:
        await self.databases.app.execute_write(
            "UPDATE jobs SET state = ?, completed_at = ?, outcome = ? WHERE operation_id = ?",
            (state, completed_at, outcome, operation_id),
        )

    async def mark_running_interrupted(self, *, reason: str) -> int:
        return await self.databases.app.execute_write(
            "UPDATE jobs SET state = 'interrupted', interruption_reason = ? "
            "WHERE state = 'running'",
            (reason,),
        )

    async def interrupt(self, *, operation_id: str, reason: str) -> None:
        """Mark one running operation interrupted during an in-memory sweep."""
        await self.databases.app.execute_write(
            "UPDATE jobs SET state = 'interrupted', interruption_reason = ? "
            "WHERE operation_id = ? AND state = 'running'",
            (reason, operation_id),
        )

    async def append_replay_audit(self, record: Mapping[str, Any]) -> None:
        """Persist one replay audit record through the application database."""
        replay_id = record.get("replay_id")
        occurred_at = record.get("occurred_at")
        if not isinstance(replay_id, str) or not replay_id:
            raise ValueError("replay audit requires a replay_id")
        if not isinstance(occurred_at, datetime):
            raise TypeError("replay audit occurred_at must be a datetime")
        payload = dict(record)
        payload["target"] = str(payload["target"]) if payload.get("target") is not None else None
        payload["occurred_at"] = occurred_at.isoformat()
        await self.databases.app.execute_write(
            "INSERT INTO audit_log(event_type, entity_type, entity_id, occurred_at, payload_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "ProtocolReplayAudit",
                "replay",
                replay_id,
                occurred_at.isoformat(),
                json.dumps(payload, sort_keys=True, default=str),
            ),
        )


__all__: tuple[str, ...] = ()
