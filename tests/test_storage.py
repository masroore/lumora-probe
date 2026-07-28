from pathlib import Path

import pytest

from probe_lite.storage import InvalidDatasetError, Storage


def test_path_for_uses_study_series_instance_hierarchy(tmp_path: Path) -> None:
    path = Storage(tmp_path).path_for("1.2.3", "1.2.4", "1.2.5")

    assert path == tmp_path / "1.2.3" / "1.2.4" / "1.2.5.dcm"


def test_path_for_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(InvalidDatasetError):
        Storage(tmp_path).path_for("1.2.3", "../escape", "1.2.5")


def test_raw_bytes_are_preserved(tmp_path: Path) -> None:
    raw = b"not a parseable DICOM dataset"
    stored = Storage(tmp_path).write_raw("1.2.5", raw)

    assert stored.raw is True
    assert stored.path == tmp_path / "1.2.5.dcm.raw"
    assert stored.path.read_bytes() == raw
