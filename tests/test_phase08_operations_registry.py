"""Tests for durable Phase 08 operation audit records."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumora_probe.core.config import StartupConfig
from lumora_probe.core.operations import SQLiteOperationRegistry
from lumora_probe.core.paths import DataPaths
from lumora_probe.core.storage import StorageDatabases


def _databases(tmp_path: Path) -> StorageDatabases:
    paths = DataPaths.from_config(StartupConfig(data_dir=tmp_path / "data"))
    paths.initialise(network_detector=lambda _: False)
    databases = StorageDatabases.from_paths(paths, network_detector=lambda _: False)
    databases.initialise()
    return databases


@pytest.mark.asyncio
async def test_operation_registry_persists_progress_and_interruption(tmp_path: Path) -> None:
    registry = SQLiteOperationRegistry(_databases(tmp_path))
    await registry.start(
        operation_id="op-1",
        job_type="capture-import",
        parameters={"path": "/tmp/input"},
        started_at="2026-07-29T00:00:00+00:00",
    )
    await registry.update_progress("op-1", {"done": 2, "total": 5})

    record = await registry.get("op-1")
    assert record is not None
    assert record["state"] == "running"
    assert record["progress"] == {"done": 2, "total": 5}

    assert await registry.mark_running_interrupted(reason="process restarted") == 1
    interrupted = await registry.get("op-1")
    assert interrupted is not None
    assert interrupted["state"] == "interrupted"
    assert interrupted["interruption_reason"] == "process restarted"
