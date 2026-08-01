# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lumora_probe.captures.format import (
    CaptureFidelity,
    CaptureFormatError,
    CaptureIntegrityError,
    CaptureManifest,
    CapturePackage,
    CapturePackageWriter,
    ContentAddressedObjectStore,
    FsyncPolicy,
    UnsupportedCaptureFormatError,
    pack_capture,
    unpack_capture,
)
from lumora_probe.core.errors import PathSecurityError

CAPTURE_ID = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0b5"


def manifest(*, fidelity: CaptureFidelity = CaptureFidelity.PROTOCOL) -> CaptureManifest:
    return CaptureManifest(
        capture_id=CAPTURE_ID,
        created_at=datetime(2026, 7, 29, tzinfo=UTC),
        fidelity=fidelity,
        clock_anchor={
            "wall_time": datetime(2026, 7, 29, tzinfo=UTC),
            "monotonic_ns": 100,
        },
    )


def test_capture_writer_persists_verbatim_jsonl_and_seals_object_inventory(
    tmp_path: Path,
) -> None:
    writer = CapturePackageWriter(tmp_path / "captures", manifest(), fsync_policy=FsyncPolicy.FLUSH)
    raw_event = b'{"event_name":"AssociationStarted","sequence":1}'
    writer.append_event_raw(raw_event)
    writer.append_pdu({"direction": "inbound", "length": 42})
    object_entry = writer.put_object(
        b"dicom-bytes",
        study_uid="1.2.3",
        series_uid="1.2.3.4",
        sop_instance_uid="1.2.3.4.5",
        transfer_syntax_uid="1.2.840.10008.1.2.1",
    )
    sealed = writer.seal(completed_at=datetime(2026, 7, 29, 1, tzinfo=UTC))

    package = CapturePackage.open(tmp_path / "captures" / CAPTURE_ID)
    assert package.manifest == sealed
    assert (package.path / "events.jsonl").read_bytes() == raw_event + b"\n"
    assert json.loads((package.path / "pdus.jsonl").read_text()) == {
        "direction": "inbound",
        "length": 42,
    }
    assert package.manifest.objects[0] == object_entry
    assert package.verify().valid is True


def test_content_addressed_store_deduplicates_and_detects_tampering(tmp_path: Path) -> None:
    store = ContentAddressedObjectStore(tmp_path / "objects")
    digest = store.put(b"same bytes")
    assert store.put(b"same bytes") == digest
    assert store.digests() == (digest,)
    assert store.verify(digest) is True

    store.path_for(digest).write_bytes(b"tampered")
    assert store.verify(digest) is False


def test_capture_integrity_report_identifies_missing_and_changed_objects(tmp_path: Path) -> None:
    writer = CapturePackageWriter(tmp_path / "captures", manifest())
    item = writer.put_object(
        b"payload",
        study_uid="1",
        series_uid="2",
        sop_instance_uid="3",
    )
    writer.seal()
    object_path = writer.objects.path_for(item.digest)
    object_path.write_bytes(b"changed")

    package = CapturePackage.open(writer.capture_path)
    report = package.verify()
    assert report.valid is False
    assert report.mismatched == (item.digest,)
    with pytest.raises(CaptureIntegrityError):
        package.verify_or_raise()


def test_lpcap_pack_and_unpack_round_trip(tmp_path: Path) -> None:
    source_root = tmp_path / "captures"
    writer = CapturePackageWriter(source_root, manifest())
    writer.append_event({"event_name": "CaptureStarted", "sequence": 1})
    writer.seal()
    archive_path = pack_capture(writer.capture_path, tmp_path / "capture.lpcap")
    unpacked_root = unpack_capture(archive_path, tmp_path / "unpacked")

    unpacked = CapturePackage.open(unpacked_root)
    assert unpacked.manifest.capture_id == CAPTURE_ID
    assert (unpacked.path / "events.jsonl").is_file()
    assert zipfile.is_zipfile(archive_path)


def test_unpack_rejects_zip_slip(tmp_path: Path) -> None:
    archive_path = tmp_path / "malicious.lpcap"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../../outside.txt", "bad")
    with pytest.raises(PathSecurityError):
        unpack_capture(archive_path, tmp_path / "unpacked")


def test_manifest_rejects_future_format_and_invalid_capture_id(tmp_path: Path) -> None:
    future = manifest().model_copy(update={"format_version": 99})
    path = tmp_path / "future"
    path.mkdir()
    (path / "manifest.json").write_text(future.model_dump_json(), encoding="utf-8")
    with pytest.raises(UnsupportedCaptureFormatError):
        CapturePackage.open(path)

    with pytest.raises(ValueError):
        CaptureManifest(
            capture_id="not-a-uuid",
            created_at=datetime(2026, 7, 29, tzinfo=UTC),
            fidelity=CaptureFidelity.EVENTS,
        )


def test_jsonl_writer_rejects_embedded_newlines(tmp_path: Path) -> None:
    writer = CapturePackageWriter(tmp_path / "captures", manifest())
    with pytest.raises(CaptureFormatError):
        writer.append_event_raw(b'{"event_name":"bad"}\n{"event_name":"second"}')
