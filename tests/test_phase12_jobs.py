"""Phase 12 in-memory job registry acceptance tests."""

from __future__ import annotations

import asyncio

import pytest

from lumora_probe.core.operations import InMemoryJobRegistry, JobState
from tests.doubles.ids import SeededIdGenerator

JOB_ID = "018f0d4e-7b6a-7000-8000-000000000301"


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
