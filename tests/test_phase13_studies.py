# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Phase 13 projection provenance and folder import tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from lumora_probe.studies.contracts import FolderImportObject, InstanceRetention
from lumora_probe.studies.repository import InstanceProjection
from lumora_probe.studies.service import FolderImportService, StudyBrowserService
from lumora_probe.web.api import create_app
from tests.test_phase13_decode import make_dicom


def instance(capture: str, digest: str, uid: str = "sop-1") -> InstanceProjection:
    return InstanceProjection(
        capture_id=capture,
        study_uid="study-1",
        series_uid="series-1",
        sop_instance_uid=uid,
        object_digest=digest,
        object_path=f"objects/{digest}",
        transfer_syntax_uid="1.2.840.10008.1.2.1",
        rows=2,
        columns=2,
        created_at=datetime(2026, 7, 30, tzinfo=UTC),
    )


def test_study_browser_surfaces_capture_provenance_and_duplicate_finding() -> None:
    rows = [instance("capture-b", "b" * 64), instance("capture-a", "a" * 64)]

    provenance = StudyBrowserService.provenance(rows)
    findings = StudyBrowserService.duplicate_findings(rows)

    assert provenance[0].present_in_capture_count == 2
    assert provenance[0].capture_ids == ("capture-a", "capture-b")
    assert provenance[0].duplicate
    assert findings[0].object_digests == ("a" * 64, "b" * 64)
    assert findings[0].capture_ids == ("capture-a", "capture-b")


@pytest.mark.asyncio
async def test_folder_import_materializes_objects_fidelity(tmp_path: Path) -> None:
    source = tmp_path / "input"
    source.mkdir()
    (source / "one.dcm").write_bytes(b"not-a-dicom")

    class Writer:
        async def write_synthetic_capture(
            self, objects: tuple[FolderImportObject, ...], *, fidelity: str
        ) -> str:
            assert len(objects) == 1
            assert fidelity == "objects"
            return "018f0d4e-7b6a-7000-8000-000000000801"

    with pytest.raises(ValueError, match="invalid DICOM"):
        await FolderImportService(Writer()).import_folder(source)

    (source / "one.dcm").write_bytes(make_dicom())
    result = await FolderImportService(Writer()).import_folder(source)
    assert result.fidelity == "objects"
    assert result.capture_id == "018f0d4e-7b6a-7000-8000-000000000801"
    assert len(result.objects) == 1


@pytest.mark.asyncio
async def test_study_browser_endpoint_exposes_partial_provenance() -> None:
    class Provider:
        async def get_study_browser(self, study_uid: str):
            return {
                "study_uid": study_uid,
                "partial": True,
                "present_in_capture_count": 3,
                "instances": [],
                "duplicate_findings": [],
            }

    application = create_app(study_browser_provider=Provider())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        response = await client.get("/api/v1/studies/study-1/browser")

    assert response.status_code == 200
    assert response.json()["partial"] is True
    assert response.json()["present_in_capture_count"] == 3


def test_study_browser_exposes_ring_buffer_retention_and_promotion_window() -> None:
    row = instance("capture-ring", "r" * 64)
    retention = {
        row.object_digest: InstanceRetention(
            source="ring-buffer",
            expires_at=datetime(2026, 7, 30, 0, 5, tzinfo=UTC),
            promotion_start=datetime(2026, 7, 30, 0, tzinfo=UTC),
            promotion_end=datetime(2026, 7, 30, 0, 1, tzinfo=UTC),
            aggregate_id="association-1",
        )
    }

    browser = StudyBrowserService.browser("study-1", [row], retention)

    assert browser["instances"][0]["retention"] == {
        "source": "ring-buffer",
        "state": "retained",
        "expires_at": "2026-07-30T00:05:00+00:00",
        "promotion_start": "2026-07-30T00:00:00+00:00",
        "promotion_end": "2026-07-30T00:01:00+00:00",
        "aggregate_id": "association-1",
        "promotable": True,
    }


@pytest.mark.asyncio
async def test_metadata_inspector_filters_private_tags_and_searches() -> None:
    from lumora_probe.studies.contracts import DicomObjectSource
    from lumora_probe.studies.service import MetadataInspectorService

    result = await MetadataInspectorService().inspect(
        DicomObjectSource(
            object_digest="m" * 64,
            raw_bytes=make_dicom(),
            instance_id="instance-1",
        ),
        query="SOPInstanceUID",
    )

    assert result.instance_id == "instance-1"
    assert len(result.tags) == 1
    assert result.tags[0].keyword == "SOPInstanceUID"
    assert "(0008,0018)" in result.raw_dump


@pytest.mark.asyncio
async def test_metadata_inspector_endpoint_preserves_private_toggle_and_query() -> None:
    class Provider:
        def __init__(self) -> None:
            self.calls: list[tuple[str, bool, str | None]] = []

        async def get_metadata(self, instance_id: str, *, include_private: bool, query: str | None):
            self.calls.append((instance_id, include_private, query))
            return {
                "instance_id": instance_id,
                "tags": [],
                "raw_dump": "",
            }

    provider = Provider()
    application = create_app(metadata_provider=provider)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        response = await client.get(
            "/api/v1/instances/instance-1/metadata?include_private=true&query=PatientName"
        )

    assert response.status_code == 200
    assert provider.calls == [("instance-1", True, "PatientName")]
