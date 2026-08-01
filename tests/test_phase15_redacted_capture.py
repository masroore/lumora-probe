# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Phase 15 redacted capture output tests."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.filewriter import dcmwrite
from pydicom.uid import ExplicitVRLittleEndian

from lumora_probe.captures.format import (
    CaptureFidelity,
    CaptureManifest,
    CapturePackage,
    CapturePackageWriter,
)
from lumora_probe.reports.redacted_capture import redact_capture
from tests.doubles.clock import ControllableClock
from tests.doubles.ids import SeededIdGenerator

SOURCE_ID = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0b5"
OUTPUT_ID = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0c0"


def _dataset(study: str, series: str, instance: str, patient: str) -> bytes:
    dataset = Dataset()
    dataset.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    dataset.SOPInstanceUID = instance
    dataset.StudyInstanceUID = study
    dataset.SeriesInstanceUID = series
    dataset.PatientName = patient
    dataset.PatientID = "patient-15"
    dataset.file_meta = FileMetaDataset()
    dataset.file_meta.MediaStorageSOPClassUID = dataset.SOPClassUID
    dataset.file_meta.MediaStorageSOPInstanceUID = instance
    dataset.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    buffer = BytesIO()
    dcmwrite(buffer, dataset, enforce_file_format=True)
    return buffer.getvalue()


def _source(tmp_path: Path) -> tuple[CapturePackage, bytes, bytes]:
    manifest = CaptureManifest(
        capture_id=SOURCE_ID,
        created_at=datetime(2026, 7, 29, tzinfo=UTC),
        fidelity=CaptureFidelity.OBJECTS,
        source="live",
    )
    writer = CapturePackageWriter(tmp_path / "captures", manifest)
    writer.append_event_raw(b'{"event_name":"AssociationStarted","sequence":1}\n')
    study = "1.2.826.0.1.3680043.10.543.15.1"
    series = f"{study}.1"
    first = _dataset(study, series, f"{series}.1", "Patient^One")
    second = _dataset(study, series, f"{series}.2", "Patient^Two")
    writer.put_object(first, study_uid=study, series_uid=series, sop_instance_uid=f"{series}.1")
    writer.put_object(second, study_uid=study, series_uid=series, sop_instance_uid=f"{series}.2")
    writer.seal(completed_at=datetime(2026, 7, 29, 1, tzinfo=UTC))
    package = CapturePackage.open(writer.capture_path)
    return package, (package.path / "manifest.json").read_bytes(), first


@pytest.mark.component
def test_redaction_writes_new_capture_with_shared_uid_mapping_and_provenance(
    tmp_path: Path,
) -> None:
    source, source_manifest, first = _source(tmp_path)
    source_events = (source.path / "events.jsonl").read_bytes()
    output = redact_capture(
        source,
        tmp_path / "redacted",
        id_generator=SeededIdGenerator(
            [
                OUTPUT_ID,
                "018f0c40-7d3d-7abd-8d2e-5b5a58fce0b5",
                "018f0c40-7d3d-7abe-8d2e-5b5a58fce0b5",
                "018f0c40-7d3d-7abf-8d2e-5b5a58fce0b5",
                "018f0c40-7d3d-7ac0-8d2e-5b5a58fce0b5",
            ]
        ),
        clock=ControllableClock(datetime(2026, 7, 30, 12, 0, tzinfo=UTC)),
    )

    assert output.manifest.capture_id == OUTPUT_ID
    assert output.manifest.source == "redacted"
    assert output.manifest.source_capture_id == SOURCE_ID
    assert output.manifest.redaction_profile == "default-v1"
    assert output.manifest.fidelity is CaptureFidelity.OBJECTS
    assert output.manifest.model_extra["redaction_uid_mapping_count"] == 4
    assert output.verify().valid

    output_objects = [output.objects.read(item.digest) for item in output.manifest.objects]
    from pydicom import dcmread

    datasets = [dcmread(BytesIO(value)) for value in output_objects]
    assert all(not hasattr(dataset, "PatientName") for dataset in datasets)
    assert len({dataset.StudyInstanceUID for dataset in datasets}) == 1
    assert len({dataset.SeriesInstanceUID for dataset in datasets}) == 1
    assert len({dataset.SOPInstanceUID for dataset in datasets}) == 2
    assert output.manifest.objects[0].study_uid == output.manifest.objects[1].study_uid

    assert (source.path / "manifest.json").read_bytes() == source_manifest
    assert (source.path / "events.jsonl").read_bytes() == source_events
    assert source.objects.read(source.manifest.objects[0].digest) == first


def test_redaction_refuses_event_only_capture(tmp_path: Path) -> None:
    manifest = CaptureManifest(
        capture_id=SOURCE_ID,
        created_at=datetime(2026, 7, 29, tzinfo=UTC),
        fidelity=CaptureFidelity.EVENTS,
    )
    writer = CapturePackageWriter(tmp_path / "captures", manifest)
    writer.seal(completed_at=datetime(2026, 7, 29, 1, tzinfo=UTC))

    with pytest.raises(Exception, match="no DICOM objects"):
        redact_capture(
            writer.capture_path,
            tmp_path / "redacted",
            id_generator=SeededIdGenerator([OUTPUT_ID]),
            clock=ControllableClock(datetime(2026, 7, 30, tzinfo=UTC)),
        )
