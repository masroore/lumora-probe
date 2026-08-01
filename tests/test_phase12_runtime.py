# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Phase 12 application replay composition tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from lumora_probe.associations.network import DICOMStoreResult
from lumora_probe.core.operations import InMemoryJobRegistry, SQLiteOperationRegistry
from lumora_probe.replay.contracts import ProtocolReplayDataset, ProtocolReplayPolicy
from lumora_probe.replay.service import ReplayRuntime
from lumora_probe.shared.value_objects import NetworkEndpoint
from lumora_probe.web.api import create_app
from tests.doubles.clock import ControllableClock
from tests.doubles.ids import SeededIdGenerator
from tests.test_phase12_jobs import databases

REPLAY_ID = "018f0d4e-7b6a-7000-8000-000000000601"


class FakeSender:
    async def send_dataset(self, data: bytes, *, transfer_syntax: str) -> DICOMStoreResult:
        return DICOMStoreResult(success=True, status=0x0000, duration_ns=len(data))


def policy() -> ProtocolReplayPolicy:
    target = NetworkEndpoint("127.0.0.1", 11112)
    return ProtocolReplayPolicy(target=target, allowed_targets=frozenset({target}), dry_run=False)


def dataset(index: int) -> ProtocolReplayDataset:
    return ProtocolReplayDataset(
        raw_bytes=f"dataset-{index}".encode(),
        transfer_syntax="1.2.840.10008.1.2.1",
        monotonic_ns=index,
    )


@pytest.mark.asyncio
async def test_runtime_wires_replay_to_durable_job_and_audit(tmp_path: Path) -> None:
    storage = databases(tmp_path)
    durable = SQLiteOperationRegistry(storage)
    jobs = InMemoryJobRegistry(
        durable=durable,
        id_generator=SeededIdGenerator([REPLAY_ID]),
    )
    runtime = ReplayRuntime(
        jobs,
        sender_factory=FakeSender,
        audit_store=durable,
        clock=ControllableClock(datetime(2026, 7, 30, tzinfo=UTC)),
    )

    started = await runtime.start_protocol_replay(
        [dataset(0), dataset(1)],
        policy=policy(),
        capture_fidelity="protocol",
        capture_id="capture-1",
    )
    result = await jobs.wait(started.operation_id)
    durable_result = await durable.get(REPLAY_ID)

    assert result is not None
    assert result.state.value == "completed"
    assert result.progress == {
        "planned": 2,
        "attempted": 2,
        "confirmed": 2,
        "failed": 0,
        "cancelled": False,
    }
    assert durable_result is not None
    assert durable_result["state"] == "completed"
    audit_rows = await storage.app.execute_read(
        "SELECT event_type, entity_id, payload_json FROM audit_log WHERE entity_id = ?",
        (REPLAY_ID,),
    )
    assert len(audit_rows) == 1
    assert audit_rows[0]["event_type"] == "ProtocolReplayAudit"
    assert audit_rows[0]["entity_id"] == REPLAY_ID
    assert '"confirmed_count": 2' in audit_rows[0]["payload_json"]


@pytest.mark.asyncio
async def test_runtime_startup_sweep_marks_durable_running_jobs_interrupted(tmp_path: Path) -> None:
    durable = SQLiteOperationRegistry(databases(tmp_path))
    await durable.start(
        operation_id="orphaned-replay",
        job_type="protocol-replay",
        parameters={"capture_id": "capture-1"},
        started_at="2026-07-30T00:00:00+00:00",
    )
    jobs = InMemoryJobRegistry(durable=durable)
    runtime = ReplayRuntime(
        jobs,
        sender_factory=FakeSender,
        audit_store=durable,
        clock=ControllableClock(datetime(2026, 7, 30, tzinfo=UTC)),
    )

    assert await runtime.startup() == 1
    record = await durable.get("orphaned-replay")
    assert record is not None
    assert record["state"] == "interrupted"
    assert record["interruption_reason"] == "process restarted"
    assert await runtime.startup() == 0


@pytest.mark.asyncio
async def test_web_lifespan_runs_replay_startup_sweep() -> None:
    class Runtime:
        def __init__(self) -> None:
            self.calls = 0

        async def startup(self) -> int:
            self.calls += 1
            return 0

    runtime = Runtime()
    application = create_app(replay_runtime=runtime)

    async with application.router.lifespan_context(application):
        pass

    assert runtime.calls == 1
