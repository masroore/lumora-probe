# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Phase 12 in-memory job registry acceptance tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from lumora_probe.core.config import StartupConfig
from lumora_probe.core.operations import InMemoryJobRegistry, JobState, SQLiteOperationRegistry
from lumora_probe.core.paths import DataPaths
from lumora_probe.core.storage import StorageDatabases
from lumora_probe.shared.events import EventEnvelope
from tests.doubles.ids import SeededIdGenerator

JOB_ID = "018f0d4e-7b6a-7000-8000-000000000301"
PROGRESS_EVENT_ID = "018f0d4e-7b6a-7000-8000-000000000302"


class FakeProgressPublisher:
    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []

    async def publish(
        self, event: EventEnvelope, *, capture_id: str | None = None
    ) -> EventEnvelope:
        self.events.append(event)
        return event


def databases(tmp_path: Path) -> StorageDatabases:
    paths = DataPaths.from_config(StartupConfig(data_dir=tmp_path / "data"))
    paths.initialise(network_detector=lambda _: False)
    result = StorageDatabases.from_paths(paths, network_detector=lambda _: False)
    result.initialise()
    return result


@pytest.mark.asyncio
async def test_in_memory_job_registry_runs_worker_and_keeps_progress() -> None:
    registry = InMemoryJobRegistry(id_generator=SeededIdGenerator([JOB_ID]))
    finished = asyncio.Event()

    async def worker(context):
        await context.report_progress({"confirmed": 1, "total": 2})
        finished.set()
        return "confirmed=1"

    started = await registry.start("protocol-replay", worker, parameters={"dry_run": False})
    assert started.operation_id == JOB_ID
    assert started.state is JobState.RUNNING

    await finished.wait()
    result = await registry.wait(JOB_ID)

    assert result is not None
    assert result.state is JobState.COMPLETED
    assert result.outcome == "confirmed=1"
    assert result.progress == {"confirmed": 1, "total": 2}


@pytest.mark.asyncio
async def test_in_memory_job_registry_cancellation_is_cooperative() -> None:
    registry = InMemoryJobRegistry(id_generator=SeededIdGenerator([JOB_ID]))
    started = asyncio.Event()

    async def worker(context):
        started.set()
        while not context.cancellation.is_cancelled:
            await asyncio.sleep(0)
        return "confirmed=2"

    await registry.start("protocol-replay", worker)
    await started.wait()
    assert await registry.cancel(JOB_ID)

    result = await registry.wait(JOB_ID)
    assert result is not None
    assert result.state is JobState.CANCELLED
    assert result.outcome == "confirmed=2"
    assert not await registry.cancel(JOB_ID)


@pytest.mark.asyncio
async def test_in_memory_job_registry_interrupts_running_jobs() -> None:
    registry = InMemoryJobRegistry(id_generator=SeededIdGenerator([JOB_ID]))
    started = asyncio.Event()

    async def worker(context):
        started.set()
        await context.cancellation.wait()
        return "interrupted-worker-return"

    await registry.start("protocol-replay", worker)
    await started.wait()
    assert await registry.interrupt_running("process restarted") == 1

    result = await registry.wait(JOB_ID)
    assert result is not None
    assert result.state is JobState.INTERRUPTED
    assert result.interruption_reason == "process restarted"


@pytest.mark.asyncio
async def test_in_memory_job_registry_persists_durable_audit_and_checkpoints(
    tmp_path: Path,
) -> None:
    durable = SQLiteOperationRegistry(databases(tmp_path))
    registry = InMemoryJobRegistry(
        id_generator=SeededIdGenerator([JOB_ID]),
        durable=durable,
    )

    async def worker(context):
        await context.report_progress({"confirmed": 2, "total": 2})
        return "confirmed=2"

    await registry.start("protocol-replay", worker, parameters={"capture_id": "capture-1"})
    result = await registry.wait(JOB_ID)
    durable_record = await durable.get(JOB_ID)

    assert result is not None
    assert result.state is JobState.COMPLETED
    assert durable_record is not None
    assert durable_record["job_type"] == "protocol-replay"
    assert durable_record["parameters"] == {"capture_id": "capture-1"}
    assert durable_record["state"] == "completed"
    assert durable_record["progress"] == {"confirmed": 2, "total": 2}
    assert durable_record["outcome"] == "confirmed=2"


@pytest.mark.asyncio
async def test_in_memory_job_registry_publishes_progress_on_event_bus() -> None:
    publisher = FakeProgressPublisher()
    registry = InMemoryJobRegistry(
        id_generator=SeededIdGenerator([JOB_ID, PROGRESS_EVENT_ID]),
        progress_publisher=publisher,
    )

    async def worker(context):
        await context.report_progress({"confirmed": 1, "total": 1})
        return "confirmed=1"

    await registry.start("protocol-replay", worker)
    await registry.wait(JOB_ID)

    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.event_name == "ReplayProgressed"
    assert event.aggregate_id == JOB_ID
    assert event.payload == {
        "operation_id": JOB_ID,
        "job_type": "protocol-replay",
        "confirmed": 1,
        "total": 1,
    }


@pytest.mark.asyncio
async def test_in_memory_job_registry_refuses_over_limit_job_type() -> None:
    registry = InMemoryJobRegistry(
        id_generator=SeededIdGenerator([JOB_ID, PROGRESS_EVENT_ID]),
        concurrency_limits={"protocol-replay": 1},
    )
    started = asyncio.Event()

    async def worker(context):
        started.set()
        await context.cancellation.wait()
        return "done"

    await registry.start("protocol-replay", worker)
    await started.wait()
    with pytest.raises(RuntimeError, match="concurrency limit"):
        await registry.start("protocol-replay", worker)

    assert await registry.cancel(JOB_ID)
    await registry.wait(JOB_ID)
    replacement = await registry.start("protocol-replay", lambda _: asyncio.sleep(0))
    assert replacement.operation_id == PROGRESS_EVENT_ID
    await registry.wait(PROGRESS_EVENT_ID)
