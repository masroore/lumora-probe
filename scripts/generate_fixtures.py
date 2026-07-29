"""Generate synthetic DICOM studies for tests.

This script creates deterministic, non-clinical datasets. It must never be changed to
copy or anonymize clinical data into the repository.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage

STUDY_UID = "1.2.826.0.1.3680043.10.543.100"
PATIENT_ID = "SYNTHETIC-001"


def _dataset(*, series_number: int, instance_number: int) -> FileDataset:
    series_uid = f"1.2.826.0.1.3680043.10.543.10{series_number}"
    instance_uid = f"1.2.826.0.1.3680043.10.543.10{series_number}{instance_number}"
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = instance_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = "1.2.826.0.1.3680043.10.543.1"

    dataset = FileDataset(
        None,
        {},
        file_meta=file_meta,
        preamble=b"\0" * 128,
    )
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.SOPInstanceUID = instance_uid
    dataset.StudyInstanceUID = STUDY_UID
    dataset.SeriesInstanceUID = series_uid
    dataset.PatientName = "SYNTHETIC^TEST"
    dataset.PatientID = PATIENT_ID
    dataset.StudyDescription = "Lumora Probe synthetic fixture"
    dataset.Modality = "OT"
    dataset.SeriesNumber = series_number
    dataset.InstanceNumber = instance_number
    dataset.Rows = 16
    dataset.Columns = 16
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.BitsAllocated = 8
    dataset.BitsStored = 8
    dataset.HighBit = 7
    dataset.PixelRepresentation = 0
    dataset.PixelData = bytes((series_number + instance_number) % 256 for _ in range(16 * 16))
    return dataset


def generate_study(output_dir: Path) -> tuple[Path, ...]:
    """Write one synthetic study and return generated paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for series_number, instance_count in ((1, 2), (2, 1)):
        series_dir = output_dir / f"series-{series_number:02d}"
        series_dir.mkdir(exist_ok=True)
        for instance_number in range(1, instance_count + 1):
            path = series_dir / f"instance-{instance_number:02d}.dcm"
            _dataset(series_number=series_number, instance_number=instance_number).save_as(
                path,
                enforce_file_format=True,
            )
            paths.append(path)
    return tuple(paths)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        type=Path,
        help="directory to receive the generated synthetic study",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    paths = generate_study(args.output)
    print(f"generated {len(paths)} synthetic DICOM instances in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
