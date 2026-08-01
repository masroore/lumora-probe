"""Tests for sender_lite.catalog module."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import (
    ExplicitVRLittleEndian,
    generate_uid,
)

from sender_lite.catalog import (
    REASON_CONFLICT,
    REASON_INVALID_TRANSFER_SYNTAX,
    REASON_MISSING_UID,
    REASON_SOP_INSTANCE_MISMATCH,
    REASON_SOP_MISMATCH,
    CatalogError,
    build_catalog,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STUDY_A = "1.2.3.4.5.100"
STUDY_B = "1.2.3.4.5.200"
SERIES_A1 = "1.2.3.4.5.100.1"
SERIES_A2 = "1.2.3.4.5.100.2"
SERIES_B1 = "1.2.3.4.5.200.1"
SOP_CLASS = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage


def _make_dicom(
    path: Path,
    study_uid: str = STUDY_A,
    series_uid: str = SERIES_A1,
    sop_instance_uid: str | None = None,
    sop_class_uid: str = SOP_CLASS,
    transfer_syntax: str = ExplicitVRLittleEndian,
    instance_number: int | None = None,
    *,
    fm_sop_instance: str | None = None,
    fm_sop_class: str | None = None,
    omit_study: bool = False,
    omit_series: bool = False,
    omit_sop: bool = False,
    omit_sop_class: bool = False,
    omit_fm_sop_instance: bool = False,
    omit_fm_sop_class: bool = False,
    omit_ts: bool = False,
) -> Path:
    if sop_instance_uid is None:
        sop_instance_uid = generate_uid()
    if fm_sop_instance is None:
        fm_sop_instance = sop_instance_uid
    if fm_sop_class is None:
        fm_sop_class = sop_class_uid

    file_meta = FileMetaDataset()
    if not omit_fm_sop_instance:
        file_meta.MediaStorageSOPInstanceUID = fm_sop_instance
    if not omit_fm_sop_class:
        file_meta.MediaStorageSOPClassUID = fm_sop_class
    if not omit_ts:
        file_meta.TransferSyntaxUID = transfer_syntax
    file_meta.SourceApplicationEntityTitle = "LUMORA"

    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\x00" * 128)
    if not omit_study:
        ds.StudyInstanceUID = study_uid
    if not omit_series:
        ds.SeriesInstanceUID = series_uid
    if not omit_sop:
        ds.SOPInstanceUID = sop_instance_uid
    if not omit_sop_class:
        ds.SOPClassUID = sop_class_uid
    ds.Modality = "CT"
    if instance_number is not None:
        ds.InstanceNumber = instance_number
    # Preserve intentionally mismatched file-meta values by using the legacy-compatible
    # un-enforced file format path without deprecated writer arguments.
    mismatch = (fm_sop_class is not None and fm_sop_class != sop_class_uid) or (
        fm_sop_instance is not None and fm_sop_instance != sop_instance_uid
    )
    ds.save_as(path, enforce_file_format=not mismatch)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_arbitrary_extensions_accepted(tmp_path: Path) -> None:
    """DICOM files with .txt, .bin, and no extension are admitted."""
    _make_dicom(tmp_path / "a.txt", sop_instance_uid="1.2.3.100.1")
    _make_dicom(tmp_path / "b.bin", sop_instance_uid="1.2.3.100.2")
    _make_dicom(tmp_path / "c", sop_instance_uid="1.2.3.100.3")

    catalog = build_catalog(tmp_path)
    assert catalog.sendable_count == 3
    assert catalog.scanned_count == 3


def test_non_dicom_bytes_skipped(tmp_path: Path) -> None:
    """Random bytes that are not DICOM become a CatalogIssue."""
    (tmp_path / "garbage.dcm").write_bytes(b"not a dicom file at all")
    _make_dicom(tmp_path / "good.dcm", sop_instance_uid="1.2.3.100.1")

    catalog = build_catalog(tmp_path)
    assert catalog.sendable_count == 1
    assert catalog.scanned_count == 2
    assert len(catalog.issues) == 1
    assert catalog.issues[0].path.name == "garbage.dcm"


def test_missing_study_uid_rejected(tmp_path: Path) -> None:
    _make_dicom(tmp_path / "a.dcm", omit_study=True, sop_instance_uid="1.2.3.100.1")
    catalog = build_catalog(tmp_path)
    assert catalog.sendable_count == 0
    assert catalog.rejected_count == 1
    assert catalog.issues[0].reason == REASON_MISSING_UID


def test_missing_series_uid_rejected(tmp_path: Path) -> None:
    _make_dicom(tmp_path / "a.dcm", omit_series=True, sop_instance_uid="1.2.3.100.1")
    catalog = build_catalog(tmp_path)
    assert catalog.sendable_count == 0
    assert catalog.issues[0].reason == REASON_MISSING_UID


def test_missing_sop_uid_rejected(tmp_path: Path) -> None:
    _make_dicom(tmp_path / "a.dcm", omit_sop=True)
    catalog = build_catalog(tmp_path)
    assert catalog.sendable_count == 0
    assert catalog.issues[0].reason == REASON_MISSING_UID


def test_missing_sop_class_uid_rejected(tmp_path: Path) -> None:
    _make_dicom(tmp_path / "a.dcm", omit_sop_class=True, sop_instance_uid="1.2.3.100.1")
    catalog = build_catalog(tmp_path)
    assert catalog.sendable_count == 0
    assert catalog.issues[0].reason == REASON_MISSING_UID


def test_sop_class_mismatch_rejected(tmp_path: Path) -> None:
    _make_dicom(
        tmp_path / "a.dcm",
        sop_instance_uid="1.2.3.100.1",
        sop_class_uid=SOP_CLASS,
        fm_sop_class="1.2.840.10008.5.1.4.1.1.4",  # different
    )
    catalog = build_catalog(tmp_path)
    assert catalog.sendable_count == 0
    assert catalog.issues[0].reason == REASON_SOP_MISMATCH


def test_sop_instance_mismatch_rejected(tmp_path: Path) -> None:
    _make_dicom(
        tmp_path / "a.dcm",
        sop_instance_uid="1.2.3.100.1",
        fm_sop_instance="1.2.3.100.999",
    )
    catalog = build_catalog(tmp_path)
    assert catalog.sendable_count == 0
    assert catalog.issues[0].reason == REASON_SOP_INSTANCE_MISMATCH


def test_invalid_transfer_syntax_rejected(tmp_path: Path) -> None:
    _make_dicom(
        tmp_path / "a.dcm",
        sop_instance_uid="1.2.3.100.1",
        transfer_syntax="1.2.3.999",  # not a transfer syntax
    )
    with pytest.warns(UserWarning, match="Expected explicit VR"):
        catalog = build_catalog(tmp_path)
    assert catalog.sendable_count == 0
    assert catalog.issues[0].reason == REASON_INVALID_TRANSFER_SYNTAX


def test_duplicate_sop_instance_uid_across_dirs(tmp_path: Path) -> None:
    """All copies of a duplicated SOP Instance UID are excluded."""
    d1 = tmp_path / "dir1"
    d2 = tmp_path / "dir2"
    d1.mkdir()
    d2.mkdir()
    sop = "1.2.3.100.1"
    _make_dicom(d1 / "a.dcm", sop_instance_uid=sop)
    _make_dicom(d2 / "b.dcm", sop_instance_uid=sop)
    # Add a unique one to confirm catalog otherwise works
    _make_dicom(d1 / "c.dcm", sop_instance_uid="1.2.3.100.2")

    catalog = build_catalog(tmp_path)
    assert catalog.sendable_count == 1
    conflicts = [i for i in catalog.issues if i.reason == REASON_CONFLICT]
    assert len(conflicts) == 2
    assert {c.path.name for c in conflicts} == {"a.dcm", "b.dcm"}
    for c in conflicts:
        assert c.sop_instance_uid == sop


def test_same_study_across_dirs_merges(tmp_path: Path) -> None:
    d1 = tmp_path / "dir1"
    d2 = tmp_path / "dir2"
    d1.mkdir()
    d2.mkdir()
    _make_dicom(
        d1 / "a.dcm",
        study_uid=STUDY_A,
        series_uid=SERIES_A1,
        sop_instance_uid="1.2.3.100.1",
    )
    _make_dicom(
        d2 / "b.dcm",
        study_uid=STUDY_A,
        series_uid=SERIES_A1,
        sop_instance_uid="1.2.3.100.2",
    )

    catalog = build_catalog(tmp_path)
    assert catalog.study_count == 1
    assert catalog.sendable_count == 2
    assert catalog.studies[0].study_uid == STUDY_A
    assert len(catalog.studies[0].series) == 1
    assert len(catalog.studies[0].series[0].instances) == 2


def test_deterministic_ordering(tmp_path: Path) -> None:
    """Study/Series ascending UID; instances numbered first, then unnumbered."""
    # Study B first to verify sort
    _make_dicom(
        tmp_path / "b1.dcm",
        study_uid=STUDY_B,
        series_uid=SERIES_B1,
        sop_instance_uid="1.2.3.200.1.9",
        instance_number=1,
    )
    # Study A, series 2
    _make_dicom(
        tmp_path / "a2.dcm",
        study_uid=STUDY_A,
        series_uid=SERIES_A2,
        sop_instance_uid="1.2.3.100.2.5",
    )
    # Study A, series 1, numbered
    _make_dicom(
        tmp_path / "a1_num.dcm",
        study_uid=STUDY_A,
        series_uid=SERIES_A1,
        sop_instance_uid="1.2.3.100.1.9",
        instance_number=2,
    )
    _make_dicom(
        tmp_path / "a1_num2.dcm",
        study_uid=STUDY_A,
        series_uid=SERIES_A1,
        sop_instance_uid="1.2.3.100.1.1",
        instance_number=1,
    )
    # Unnumbered in series 1
    _make_dicom(
        tmp_path / "a1_un.dcm",
        study_uid=STUDY_A,
        series_uid=SERIES_A1,
        sop_instance_uid="1.2.3.100.1.5",
    )

    catalog = build_catalog(tmp_path)
    assert catalog.study_count == 2
    assert catalog.studies[0].study_uid == STUDY_A
    assert catalog.studies[1].study_uid == STUDY_B

    study_a = catalog.studies[0]
    assert study_a.series[0].series_uid == SERIES_A1
    assert study_a.series[1].series_uid == SERIES_A2

    # Series A1 instances: numbered first (1, 2), then unnumbered
    insts = study_a.series[0].instances
    assert [i.instance_number for i in insts] == [1, 2, None]
    # Unnumbered sorted by SOP UID
    assert insts[2].sop_instance_uid == "1.2.3.100.1.5"


def test_symlinks_skipped(tmp_path: Path) -> None:
    real = tmp_path / "real.dcm"
    _make_dicom(real, sop_instance_uid="1.2.3.100.1")
    link = tmp_path / "link.dcm"
    os.symlink(real, link)

    catalog = build_catalog(tmp_path)
    assert catalog.sendable_count == 1
    assert catalog.scanned_count == 1


def test_symlinked_directory_skipped(tmp_path: Path) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    _make_dicom(real_dir / "a.dcm", sop_instance_uid="1.2.3.100.1")
    link_dir = tmp_path / "linkdir"
    os.symlink(real_dir, link_dir)

    catalog = build_catalog(tmp_path)
    assert catalog.sendable_count == 1


def test_empty_directory_empty_catalog(tmp_path: Path) -> None:
    catalog = build_catalog(tmp_path)
    assert catalog.sendable_count == 0
    assert catalog.study_count == 0
    assert catalog.series_count == 0
    assert catalog.total_bytes == 0
    assert catalog.scanned_count == 0


def test_instance_number_missing_or_invalid(tmp_path: Path) -> None:
    _make_dicom(
        tmp_path / "no_num.dcm",
        sop_instance_uid="1.2.3.100.1",
    )
    # Write a file with non-int InstanceNumber by directly manipulating bytes
    # to bypass pydicom's validation
    path_bad = tmp_path / "bad_num.dcm"
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPInstanceUID = "1.2.3.100.2"
    file_meta.MediaStorageSOPClassUID = SOP_CLASS
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(str(path_bad), {}, file_meta=file_meta, preamble=b"\x00" * 128)
    ds.StudyInstanceUID = STUDY_A
    ds.SeriesInstanceUID = SERIES_A1
    ds.SOPInstanceUID = "1.2.3.100.2"
    ds.SOPClassUID = SOP_CLASS
    ds.save_as(path_bad, enforce_file_format=False)

    # Now manually patch the InstanceNumber in the file
    # Read the file, find a good place to insert the element
    with open(path_bad, "rb") as f:
        data = f.read()

    # InstanceNumber tag: (0020,0013), VR=IS, length=12, value="not_a_number"
    # Group=0x0020, Element=0x0013
    tag_bytes = b"\x20\x00\x13\x00"  # little endian
    vr_bytes = b"IS"
    length_bytes = b"\x0c\x00\x00\x00"  # 12 bytes
    value_bytes = b"not_a_number"
    new_element = tag_bytes + vr_bytes + length_bytes + value_bytes

    # Insert before the end of file (before any trailing padding)
    # Find a safe insertion point - after the last data element
    patched_data = data + new_element

    with open(path_bad, "wb") as f:
        f.write(patched_data)

    with pytest.warns(UserWarning, match="Invalid value for VR IS"):
        catalog = build_catalog(tmp_path)
    assert catalog.sendable_count == 2
    by_sop = {i.sop_instance_uid: i for i in catalog.studies[0].instances}
    assert by_sop["1.2.3.100.1"].instance_number is None
    assert by_sop["1.2.3.100.2"].instance_number is None


def test_stop_before_pixels_true(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify pydicom.dcmread is called with stop_before_pixels=True."""
    _make_dicom(tmp_path / "a.dcm", sop_instance_uid="1.2.3.100.1")

    import sender_lite.catalog as cat_mod

    original = cat_mod.dcmread
    calls: list[tuple[object, dict]] = []

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(cat_mod, "dcmread", spy)
    build_catalog(tmp_path)

    assert len(calls) == 1
    _, kwargs = calls[0]
    assert kwargs.get("stop_before_pixels") is True
    assert kwargs.get("force") is False


def test_catalog_aggregates(tmp_path: Path) -> None:
    _make_dicom(
        tmp_path / "a.dcm",
        study_uid=STUDY_A,
        series_uid=SERIES_A1,
        sop_instance_uid="1.2.3.100.1",
    )
    _make_dicom(
        tmp_path / "b.dcm",
        study_uid=STUDY_A,
        series_uid=SERIES_A2,
        sop_instance_uid="1.2.3.100.2",
    )
    _make_dicom(
        tmp_path / "c.dcm",
        study_uid=STUDY_B,
        series_uid=SERIES_B1,
        sop_instance_uid="1.2.3.100.3",
    )

    catalog = build_catalog(tmp_path)
    assert catalog.study_count == 2
    assert catalog.series_count == 3
    assert catalog.sendable_count == 3
    assert catalog.total_bytes == sum(i.size_bytes for i in catalog.studies[0].instances) + sum(
        i.size_bytes for i in catalog.studies[1].instances
    )


def test_presentation_requirements(tmp_path: Path) -> None:
    _make_dicom(
        tmp_path / "a.dcm",
        study_uid=STUDY_A,
        series_uid=SERIES_A1,
        sop_instance_uid="1.2.3.100.1",
        transfer_syntax=ExplicitVRLittleEndian,
    )
    catalog = build_catalog(tmp_path)
    reqs = catalog.studies[0].presentation_requirements
    assert (SOP_CLASS, ExplicitVRLittleEndian) in reqs


def test_input_root_not_exists_raises() -> None:
    with pytest.raises(CatalogError):
        build_catalog(Path("/nonexistent/path/xyz"))


def test_input_root_is_symlink_raises(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    os.symlink(real, link)
    with pytest.raises(CatalogError):
        build_catalog(link)
