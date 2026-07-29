"""DICOM dataset persistence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

UID_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+)+$")


class StorageError(Exception):
    """A dataset could not be persisted."""


class InvalidDatasetError(StorageError):
    """Required DICOM identifiers are absent or unsafe."""


@dataclass(frozen=True, slots=True)
class StoredInstance:
    path: Path
    size: int
    raw: bool = False


class Storage:
    def __init__(self, output: Path) -> None:
        self.output = Path(output)

    def path_for(self, study_uid: str, series_uid: str, sop_uid: str, suffix: str = ".dcm") -> Path:
        components = [_safe_uid(study_uid), _safe_uid(series_uid), _safe_uid(sop_uid)]
        return self.output.joinpath(*components[:-1], components[-1] + suffix)

    def write_dataset(self, dataset: Any, file_meta: Any = None) -> StoredInstance:
        """Serialize a parsed pydicom dataset with its negotiated file meta."""
        try:
            study_uid = str(dataset.StudyInstanceUID)
            series_uid = str(dataset.SeriesInstanceUID)
            sop_uid = str(dataset.SOPInstanceUID)
        except (AttributeError, KeyError, TypeError) as exc:
            raise InvalidDatasetError(
                "dataset is missing Study, Series, or SOP Instance UID"
            ) from exc
        path = self.path_for(study_uid, series_uid, sop_uid)
        if file_meta is not None:
            dataset.file_meta = file_meta
        try:
            from pydicom.filewriter import dcmwrite

            path.parent.mkdir(parents=True, exist_ok=True)
            dcmwrite(path, dataset, enforce_file_format=False)
            return StoredInstance(path=path, size=path.stat().st_size)
        except InvalidDatasetError:
            raise
        except Exception as exc:
            raise StorageError(f"could not write {path}: {exc}") from exc

    def write_raw(self, sop_uid: str, raw_bytes: bytes) -> StoredInstance:
        """Persist undecodable request bytes using the required .dcm.raw suffix."""
        path = self.output.joinpath(_safe_uid(sop_uid) + ".dcm.raw")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw_bytes)
            return StoredInstance(path=path, size=len(raw_bytes), raw=True)
        except Exception as exc:
            raise StorageError(f"could not write raw dataset {path}: {exc}") from exc


def _safe_uid(value: str) -> str:
    if not value or len(value) > 64 or not UID_PATTERN.fullmatch(value):
        raise InvalidDatasetError(f"invalid DICOM UID: {value!r}")
    return value
