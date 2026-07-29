"""Durable operation audit records with in-memory execution state elsewhere."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import Any

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
    ) -> None:
        self.clock = clock if clock is not None else SystemClock()
        self.id_generator = id_generator if id_generator is not None else UUIDv7Generator()
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
        return count

    async def _run(self, record: JobRecord, token: CancellationToken, worker: JobWorker) -> None:
        context = JobContext(record.operation_id, token, self._progress)
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

    async def _progress(self, progress: Mapping[str, Any]) -> None:
        operation_id = asyncio.current_task()
        for record in self._records.values():
            if self._tasks.get(record.operation_id) is operation_id:
                record.progress = dict(progress)
                return

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

    async def complete(self, operation_id: str, *, completed_at: str, outcome: str) -> None:
        await self.databases.app.execute_write(
            "UPDATE jobs SET state = 'completed', completed_at = ?, outcome = ? "
            "WHERE operation_id = ?",
            (completed_at, outcome, operation_id),
        )

    async def mark_running_interrupted(self, *, reason: str) -> int:
        return await self.databases.app.execute_write(
            "UPDATE jobs SET state = 'interrupted', interruption_reason = ? "
            "WHERE state = 'running'",
            (reason,),
        )


__all__: tuple[str, ...] = ()
