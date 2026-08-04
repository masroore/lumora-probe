# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 13 file-backed instance source repository tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from lumora_probe.studies.contracts import DicomObjectSource
from lumora_probe.studies.repository import FileSystemInstanceSourceRepository

pytestmark = pytest.mark.component


class _FakeDatabases:
    """Minimal StorageDatabases double for component tests."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.last_query: tuple[str, tuple] | None = None
        self.index = self

    async def execute_read(self, sql: str, params: tuple = ()) -> list[dict]:
        self.last_query = (sql, params)
        return self._rows


def _write_object(captures_root: Path, capture_id: str, data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()
    objects_dir = captures_root / capture_id / "objects"
    objects_dir.mkdir(parents=True, exist_ok=True)
    (objects_dir / digest).write_bytes(data)
    return digest


@pytest.mark.asyncio
async def test_happy_path_returns_verified_source(tmp_path: Path) -> None:
    data = b"synthetic-dicom-bytes"
    digest = _write_object(tmp_path, "capture-1", data)
    databases = _FakeDatabases(
        [
            {
                "capture_id": "capture-1",
                "object_digest": digest,
                "object_path": f"objects/{digest}",
            }
        ]
    )
    repo = FileSystemInstanceSourceRepository(tmp_path, databases)

    source = await repo.get_instance_source("sop-instance-1")

    assert source is not None
    assert isinstance(source, DicomObjectSource)
    assert source.object_digest == digest
    assert source.raw_bytes == data
    assert source.capture_id == "capture-1"
    assert source.instance_id == "sop-instance-1"


@pytest.mark.asyncio
async def test_numeric_projection_id_resolves_verified_source(tmp_path: Path) -> None:
    data = b"synthetic-dicom-bytes"
    digest = _write_object(tmp_path, "capture-1", data)
    databases = _FakeDatabases(
        [
            {
                "capture_id": "capture-1",
                "object_digest": digest,
                "object_path": f"objects/{digest}",
            }
        ]
    )
    repo = FileSystemInstanceSourceRepository(tmp_path, databases)

    source = await repo.get_instance_source("1")

    assert source is not None
    assert source.raw_bytes == data
    assert databases.last_query is not None
    query, params = databases.last_query
    assert "CAST(i.instance_id AS TEXT)" in query
    assert params == ("1", "1")


@pytest.mark.asyncio
async def test_wrong_digest_returns_none(tmp_path: Path) -> None:
    wrong_digest = "a" * 64
    objects_dir = tmp_path / "capture-1" / "objects"
    objects_dir.mkdir(parents=True, exist_ok=True)
    (objects_dir / wrong_digest).write_bytes(b"corrupted-content")
    databases = _FakeDatabases(
        [
            {
                "capture_id": "capture-1",
                "object_digest": wrong_digest,
                "object_path": f"objects/{wrong_digest}",
            }
        ]
    )
    repo = FileSystemInstanceSourceRepository(tmp_path, databases)

    source = await repo.get_instance_source("sop-instance-1")

    assert source is None


@pytest.mark.asyncio
async def test_missing_capture_returns_none(tmp_path: Path) -> None:
    databases = _FakeDatabases(
        [
            {
                "capture_id": "nonexistent-capture",
                "object_digest": "b" * 64,
                "object_path": "objects/bbb",
            }
        ]
    )
    repo = FileSystemInstanceSourceRepository(tmp_path, databases)

    source = await repo.get_instance_source("sop-instance-1")

    assert source is None


@pytest.mark.asyncio
async def test_no_projection_row_returns_none(tmp_path: Path) -> None:
    databases = _FakeDatabases([])
    repo = FileSystemInstanceSourceRepository(tmp_path, databases)

    source = await repo.get_instance_source("unknown-instance")

    assert source is None
