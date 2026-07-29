from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lumora_probe.captures.format import CaptureFidelity, CaptureManifest, CapturePackageWriter
from lumora_probe.captures.repository import CaptureRepository
from lumora_probe.core.config import StartupConfig
from lumora_probe.core.errors import PathSecurityError
from lumora_probe.core.paths import DataPaths
from lumora_probe.core.storage import StorageDatabases
from lumora_probe.studies.repository import StudyProjectionRepository

CAPTURE_IDS = (
    "018f0c40-7d3d-7abc-8d2e-5b5a58fce0b5",
    "018f0c40-7d3d-7abd-8d2e-5b5a58fce0b5",
    "018f0c40-7d3d-7abe-8d2e-5b5a58fce0b5",
)


def create_capture(root: Path, capture_id: str, offset: int) -> None:
    created_at = datetime(2026, 7, 29, tzinfo=UTC) + timedelta(minutes=offset)
    writer = CapturePackageWriter(
        root,
        CaptureManifest(
            capture_id=capture_id,
            created_at=created_at,
            fidelity=CaptureFidelity.OBJECTS,
        ),
    )
    writer.put_object(
        f"object-{offset}".encode(),
        study_uid="1.2.840.study",
        series_uid="1.2.840.series",
        sop_instance_uid=f"1.2.840.instance.{offset}",
    )
    writer.seal()


@pytest.mark.asyncio
async def test_three_capture_study_cascade_preserves_surviving_projection(tmp_path: Path) -> None:
    paths = DataPaths.from_config(StartupConfig(data_dir=tmp_path / "data"))
    paths.initialise(network_detector=lambda _: False)
    databases = StorageDatabases.from_paths(paths, network_detector=lambda _: False)
    databases.initialise()
    for offset, capture_id in enumerate(CAPTURE_IDS):
        create_capture(paths.captures, capture_id, offset)

    captures = CaptureRepository(databases)
    await captures.rebuild(paths.captures)
    with databases.app.write_transaction() as connection:
        connection.executemany(
            "INSERT INTO bookmarks(bookmark_id, name, study_uid, capture_id, sop_instance_uid, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                (
                    "bookmark-capture",
                    "instance evidence",
                    "1.2.840.study",
                    CAPTURE_IDS[0],
                    "1.2.840.instance.0",
                    "now",
                ),
                ("bookmark-study", "whole study", "1.2.840.study", None, None, "now"),
            ),
        )

    studies = StudyProjectionRepository(databases, capture_roots=(paths.captures,))
    result = await studies.delete_capture(CAPTURE_IDS[0])

    assert result.affected_study_uids == ("1.2.840.study",)
    assert result.removed_instance_count == 1
    assert result.removed_bookmark_count == 1
    assert result.retained_study_uids == ("1.2.840.study",)
    assert [item.capture_id for item in await studies.list_instances()] == list(CAPTURE_IDS[1:])
    projection = (await studies.list_studies())[0]
    assert projection.capture_count == 2
    assert projection.instance_count == 2
    assert projection.partial is True
    assert (paths.captures / CAPTURE_IDS[0]).exists() is False

    with databases.app.connection(read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0] == 1
        assert connection.execute("SELECT name FROM bookmarks").fetchone()[0] == "whole study"
        audit = connection.execute(
            "SELECT event_type, payload_json FROM audit_log WHERE entity_id = ?",
            (CAPTURE_IDS[0],),
        ).fetchone()
        assert audit["event_type"] == "CaptureDeleted"
        assert '"removed_instance_count":1' in audit["payload_json"]

    await studies.delete_capture(CAPTURE_IDS[1])
    assert (await studies.list_studies())[0].partial is False
    await studies.delete_capture(CAPTURE_IDS[2])
    assert await studies.list_studies() == ()


@pytest.mark.asyncio
async def test_capture_deletion_refuses_unconfigured_artifact_root(tmp_path: Path) -> None:
    paths = DataPaths.from_config(StartupConfig(data_dir=tmp_path / "data"))
    paths.initialise(network_detector=lambda _: False)
    databases = StorageDatabases.from_paths(paths, network_detector=lambda _: False)
    databases.initialise()
    create_capture(paths.captures, CAPTURE_IDS[0], 0)
    await CaptureRepository(databases).rebuild(paths.captures)

    studies = StudyProjectionRepository(databases)
    with pytest.raises(PathSecurityError):
        await studies.delete_capture(CAPTURE_IDS[0])
