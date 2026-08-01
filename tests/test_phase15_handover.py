# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 15 handover export tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from lumora_probe.captures.format import (
    CaptureFidelity,
    CaptureManifest,
    CapturePackage,
    CapturePackageWriter,
)
from lumora_probe.captures.handover import (
    DEFAULT_HANDOVER_PROFILE,
    PIXEL_HANDOVER_PROFILE,
    export_handover,
)
from tests.doubles.clock import ControllableClock
from tests.doubles.ids import SeededIdGenerator

SOURCE_ID = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0b5"
EVENTS = b'{"event_name":"AssociationStarted","sequence":1}\n'
PDUS = b'{"direction":"inbound","length":42}\n'
OBJECT = b"synthetic-dicom-object\n"


def _source(tmp_path: Path) -> tuple[CapturePackage, bytes, bytes]:
    manifest = CaptureManifest(
        capture_id=SOURCE_ID,
        created_at=datetime(2026, 7, 29, tzinfo=UTC),
        fidelity=CaptureFidelity.OBJECTS,
        source="live",
        clock_anchor={
            "wall_time": datetime(2026, 7, 29, tzinfo=UTC),
            "monotonic_ns": 100,
        },
        extra_source_metadata="must not cross the handover boundary",
    )
    writer = CapturePackageWriter(tmp_path / "captures", manifest)
    writer.append_event_raw(EVENTS)
    writer.append_pdu_raw(PDUS)
    object_entry = writer.put_object(
        OBJECT,
        study_uid="1.2.3",
        series_uid="1.2.3.4",
        sop_instance_uid="1.2.3.4.5",
    )
    writer.seal(completed_at=datetime(2026, 7, 29, 1, tzinfo=UTC))
    package = CapturePackage.open(writer.capture_path)
    return (
        package,
        package.objects.path_for(object_entry.digest).read_bytes(),
        package.path.joinpath("manifest.json").read_bytes(),
    )


def _ids(value: str) -> SeededIdGenerator:
    return SeededIdGenerator([value])


@pytest.mark.component
def test_default_handover_drops_objects_and_preserves_source(tmp_path: Path) -> None:
    source, object_bytes, original_manifest = _source(tmp_path)
    source_events = (source.path / "events.jsonl").read_bytes()
    source_pdus = (source.path / "pdus.jsonl").read_bytes()
    output_id = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0c0"
    clock = ControllableClock(datetime(2026, 7, 30, 12, 0, tzinfo=UTC))

    exported = export_handover(
        source,
        tmp_path / "handover",
        id_generator=_ids(output_id),
        clock=clock,
    )

    assert exported.manifest.capture_id == output_id
    assert exported.manifest.fidelity is CaptureFidelity.EVENTS
    assert exported.manifest.source_capture_id == SOURCE_ID
    assert exported.manifest.redaction_profile == DEFAULT_HANDOVER_PROFILE
    assert exported.manifest.model_extra["handover_pixel_data_included"] is False
    assert exported.manifest.model_extra["handover_pixel_export_deliberate"] is False
    assert exported.manifest.model_extra["handover_source_fidelity"] == "objects"
    assert "extra_source_metadata" not in exported.manifest.model_extra
    assert exported.manifest.objects == ()
    assert (exported.path / "events.jsonl").read_bytes() == EVENTS
    assert (exported.path / "pdus.jsonl").read_bytes() == PDUS
    assert tuple((exported.path / "objects").iterdir()) == ()

    assert (source.path / "events.jsonl").read_bytes() == source_events
    assert (source.path / "pdus.jsonl").read_bytes() == source_pdus
    assert source.path.joinpath("manifest.json").read_bytes() == original_manifest
    assert object_bytes == OBJECT


def test_handover_output_is_deterministic_with_injected_identity_and_clock(tmp_path: Path) -> None:
    source, _, _ = _source(tmp_path)
    output_id = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0c1"
    export_time = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)

    first = export_handover(
        source,
        tmp_path / "first",
        id_generator=_ids(output_id),
        clock=ControllableClock(export_time),
    )
    second = export_handover(
        source,
        tmp_path / "second",
        id_generator=_ids(output_id),
        clock=ControllableClock(export_time),
    )

    for name in ("manifest.json", "events.jsonl", "pdus.jsonl"):
        assert (first.path / name).read_bytes() == (second.path / name).read_bytes()


def test_pixel_bearing_handover_requires_explicit_opt_in_and_is_labelled(tmp_path: Path) -> None:
    source, object_bytes, _ = _source(tmp_path)
    output_id = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0c2"

    exported = export_handover(
        source,
        tmp_path / "pixel-handover",
        id_generator=_ids(output_id),
        clock=ControllableClock(datetime(2026, 7, 30, 12, 0, tzinfo=UTC)),
        pixel_bearing=True,
    )

    assert exported.manifest.fidelity is CaptureFidelity.OBJECTS
    assert exported.manifest.redaction_profile == PIXEL_HANDOVER_PROFILE
    assert exported.manifest.model_extra["handover_pixel_data_included"] is True
    assert exported.manifest.model_extra["handover_pixel_export_deliberate"] is True
    assert len(exported.manifest.objects) == 1
    assert exported.objects.read(exported.manifest.objects[0].digest) == object_bytes
    assert source.manifest.objects
    assert source.manifest.source == "live"
