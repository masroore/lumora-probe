from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lumora_probe.captures.format import (
    CaptureFidelity,
    CaptureManifest,
    CapturePackageWriter,
    pack_capture,
)
from lumora_probe.captures.repository import (
    CaptureRepository,
    RetentionPolicy,
    capture_to_row,
    discover_capture_packages,
    row_to_capture,
)
from lumora_probe.core.config import StartupConfig
from lumora_probe.core.paths import DataPaths
from lumora_probe.core.storage import StorageDatabases

BASE_ID = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0b5"
SECOND_ID = "018f0c40-7d3d-7abd-8d2e-5b5a58fce0b5"


def make_manifest(capture_id: str, created_at: datetime) -> CaptureManifest:
    return CaptureManifest(
        capture_id=capture_id,
        created_at=created_at,
        fidelity=CaptureFidelity.PROTOCOL,
        clock_anchor={"wall_time": created_at, "monotonic_ns": 100},
    )


def write_capture(root: Path, capture_id: str, created_at: datetime, payload: bytes) -> Path:
    writer = CapturePackageWriter(root, make_manifest(capture_id, created_at))
    writer.append_event(
        {
            "event_id": f"event-{capture_id}",
            "event_name": "CStoreReceived",
            "event_version": 1,
            "observed_at": created_at.isoformat(),
            "monotonic_ns": 101,
            "origin": "observed",
        }
    )
    writer.put_object(
        payload,
        study_uid="1.2.3",
        series_uid="1.2.3.4",
        sop_instance_uid=f"1.2.3.4.{capture_id[-1]}",
        transfer_syntax_uid="1.2.840.10008.1.2.1",
    )
    writer.seal()
    return writer.capture_path


def repository_for(tmp_path: Path) -> tuple[DataPaths, CaptureRepository]:
    paths = DataPaths.from_config(StartupConfig(data_dir=tmp_path / "data"))
    paths.initialise(network_detector=lambda _: False)
    databases = StorageDatabases.from_paths(paths, network_detector=lambda _: False)
    databases.initialise()
    return paths, CaptureRepository(databases)


@pytest.mark.asyncio
async def test_rebuild_recreates_projection_byte_for_byte_and_preserves_provenance(
    tmp_path: Path,
) -> None:
    paths, repository = repository_for(tmp_path)
    write_capture(paths.captures, BASE_ID, datetime(2026, 7, 29, tzinfo=UTC), b"first")
    write_capture(
        paths.captures,
        SECOND_ID,
        datetime(2026, 7, 29, 0, 1, tzinfo=UTC),
        b"second",
    )

    first_records = await repository.rebuild(paths.captures)
    first_snapshot = await repository.projection_snapshot()
    assert len(first_records) == 2
    assert (await repository.list_captures())[0].objects[0].digest

    second_records = await repository.rebuild(paths.captures)
    second_snapshot = await repository.projection_snapshot()
    assert len(second_records) == 2
    assert first_snapshot == second_snapshot

    with repository.databases.index.connection(read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM studies").fetchone()[0] == 1
        assert (
            connection.execute("SELECT partial FROM studies WHERE study_uid = '1.2.3'").fetchone()[
                0
            ]
            == 1
        )
        assert connection.execute("SELECT COUNT(*) FROM instances").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM event_window").fetchone()[0] == 2


@pytest.mark.asyncio
async def test_torn_trailing_event_line_is_discarded_during_rebuild(tmp_path: Path) -> None:
    paths, repository = repository_for(tmp_path)
    capture_path = write_capture(
        paths.captures, BASE_ID, datetime(2026, 7, 29, tzinfo=UTC), b"first"
    )
    with (capture_path / "events.jsonl").open("ab") as handle:
        handle.write(b'{"event_name":"torn"')

    await repository.rebuild(paths.captures)
    with repository.databases.index.connection(read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM event_window").fetchone()[0] == 1


@pytest.mark.asyncio
async def test_dropped_lpcap_is_materialized_and_indexed(tmp_path: Path) -> None:
    paths, repository = repository_for(tmp_path)
    source = write_capture(paths.captures, BASE_ID, datetime(2026, 7, 29, tzinfo=UTC), b"first")
    archive = pack_capture(source, paths.captures / "incoming.lpcap")
    shutil.rmtree(source)

    discovered = discover_capture_packages(paths.captures)
    assert [package.manifest.capture_id for package, _ in discovered] == [BASE_ID]
    assert (paths.captures / BASE_ID / "manifest.json").is_file()
    await repository.rebuild(paths.captures)
    assert [record.capture_id for record in await repository.list_captures()] == [BASE_ID]
    assert archive.is_file()


@pytest.mark.asyncio
async def test_additional_read_only_capture_root_is_discovered_without_mutation(
    tmp_path: Path,
) -> None:
    paths, repository = repository_for(tmp_path)
    readonly_root = tmp_path / "handover"
    source = write_capture(readonly_root, BASE_ID, datetime(2026, 7, 29, tzinfo=UTC), b"first")
    before = (source / "manifest.json").read_bytes()

    records = await repository.rebuild(paths.captures, additional_roots=(readonly_root,))
    assert records[0].source_root == str(readonly_root.resolve())
    assert (source / "manifest.json").read_bytes() == before


@pytest.mark.asyncio
async def test_retention_selects_oldest_records_by_count_and_size(tmp_path: Path) -> None:
    paths, repository = repository_for(tmp_path)
    write_capture(paths.captures, BASE_ID, datetime(2026, 7, 29, tzinfo=UTC), b"1")
    write_capture(
        paths.captures,
        SECOND_ID,
        datetime(2026, 7, 29, 0, 1, tzinfo=UTC),
        b"22",
    )
    await repository.rebuild(paths.captures)
    assert await repository.retention_candidates(RetentionPolicy(max_captures=1)) == (BASE_ID,)
    assert await repository.retention_candidates(RetentionPolicy(max_bytes=1)) == (SECOND_ID,)


def test_capture_row_mapping_round_trip() -> None:
    created = datetime(2026, 7, 29, tzinfo=UTC)
    record = row_to_capture(
        (
            BASE_ID,
            "/captures/base",
            "/captures",
            1,
            created.isoformat(),
            None,
            "completed",
            "events",
            0,
            1,
            None,
            "digest",
            created.isoformat(),
        )
    )
    assert row_to_capture(capture_to_row(record)).capture_id == BASE_ID
    assert record.promoted_from_buffer is True
