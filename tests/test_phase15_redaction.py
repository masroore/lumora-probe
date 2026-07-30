"""Phase 15 redaction tests."""

from __future__ import annotations

from pydicom.datadict import keyword_for_tag
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import (
    ExplicitVRLittleEndian,
    SecondaryCaptureImageStorage,
    UltrasoundImageStorage,
)

from lumora_probe.reports.redaction import (
    RedactionProfile,
    redact_dataset,
)
from tests.doubles.ids import SeededIdGenerator

_UIDS = (
    "018f0c40-7d3d-7abc-8d2e-5b5a58fce0b5",
    "018f0c40-7d3d-7abd-8d2e-5b5a58fce0b5",
    "018f0c40-7d3d-7abe-8d2e-5b5a58fce0b5",
)


def seeded_ids() -> SeededIdGenerator:
    return SeededIdGenerator(_UIDS)


def dataset(*, sop_class: str = "1.2.840.10008.5.1.4.1.1.2") -> Dataset:
    value = Dataset()
    value.SOPClassUID = sop_class
    value.SOPInstanceUID = "1.2.826.0.1.3680043.10.543.15.1"
    value.StudyInstanceUID = "1.2.826.0.1.3680043.10.543.15.2"
    value.SeriesInstanceUID = "1.2.826.0.1.3680043.10.543.15.3"
    value.PatientName = "Patient^Example"
    value.PatientID = "patient-15"
    return value


def test_profile_redacts_configured_tags_on_a_deep_copy() -> None:
    source = dataset()
    source.PatientComments = "remove this comment"
    source.add_new(0x00191001, "LO", "vendor value")
    profile = RedactionProfile(
        remove_tags={"PatientName", "PatientComments"},
        replace_tags={"PatientID": "REDACTED-ID"},
        recognized_private_tags={0x00191001},
    )

    result = redact_dataset(source, seeded_ids(), profile)

    assert result.dataset is not source
    assert "PatientName" not in result.dataset
    assert "PatientComments" not in result.dataset
    assert result.dataset.PatientID == "REDACTED-ID"
    assert source.PatientName == "Patient^Example"
    assert source.PatientComments == "remove this comment"
    assert source[0x00191001].value == "vendor value"
    assert {keyword_for_tag(tag) for tag in result.redacted_tags} == {
        "PatientName",
        "PatientComments",
    }
    assert "unrecognized_private_tag" not in {warning.code for warning in result.warnings}


def test_study_series_and_sop_uids_are_consistent_and_file_meta_follows() -> None:
    source = dataset()
    source.ReferencedImageSequence = [Dataset()]
    source.ReferencedImageSequence[0].ReferencedSOPInstanceUID = source.SOPInstanceUID
    source.file_meta = FileMetaDataset()
    source.file_meta.MediaStorageSOPClassUID = source.SOPClassUID
    source.file_meta.MediaStorageSOPInstanceUID = source.SOPInstanceUID
    source.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    result = redact_dataset(source, seeded_ids(), RedactionProfile(remove_tags=()))
    output = result.dataset

    assert output.StudyInstanceUID != source.StudyInstanceUID
    assert output.SeriesInstanceUID != source.SeriesInstanceUID
    assert output.SOPInstanceUID != source.SOPInstanceUID
    assert output.file_meta.MediaStorageSOPInstanceUID == output.SOPInstanceUID
    assert output.ReferencedImageSequence[0].ReferencedSOPInstanceUID == output.SOPInstanceUID
    assert len(result.uid_mapping) == 3
    assert all(uid.startswith("2.25.") and len(uid) <= 64 for uid in result.uid_mapping.values())

    repeat = redact_dataset(source, seeded_ids(), RedactionProfile(remove_tags=()))
    assert repeat.uid_mapping == result.uid_mapping
    assert repeat.dataset.StudyInstanceUID == output.StudyInstanceUID
    assert repeat.dataset.SeriesInstanceUID == output.SeriesInstanceUID
    assert repeat.dataset.SOPInstanceUID == output.SOPInstanceUID


def test_redaction_emits_explicit_warnings_for_unverifiable_content() -> None:
    source = dataset(sop_class=str(SecondaryCaptureImageStorage))
    source.BurnedInAnnotation = "YES"
    source.PatientComments = "free text"
    source.add_new(0x00191001, "LO", "vendor identifier")

    result = redact_dataset(source, seeded_ids())
    codes = {warning.code for warning in result.warnings}
    messages = " ".join(warning.message for warning in result.warnings)

    assert "burned_in_annotation" in codes
    assert "secondary_capture_sop_class" in codes
    assert "screenshot_sop_class" in codes
    assert "unrecognized_private_tag" in codes
    assert "free_text_field" in codes
    assert "BurnedInAnnotation" in messages
    assert "screenshot" in messages.lower()
    assert "private tag" in messages.lower()
    assert "free-text" in messages.lower()


def test_ultrasound_and_screenshot_modality_are_warned() -> None:
    ultrasound = dataset(sop_class=str(UltrasoundImageStorage))
    ultrasound_result = redact_dataset(ultrasound, seeded_ids())
    assert {warning.code for warning in ultrasound_result.warnings} >= {"ultrasound_sop_class"}

    screenshot = dataset()
    screenshot.Modality = "SC"
    screenshot_result = redact_dataset(screenshot, seeded_ids())
    assert {warning.code for warning in screenshot_result.warnings} >= {"screenshot_sop_class"}
