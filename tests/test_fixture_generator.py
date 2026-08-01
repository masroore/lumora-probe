# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Tests for the synthetic DICOM fixture generator."""

from __future__ import annotations

import pytest
from pydicom import dcmread

from scripts.generate_fixtures import STUDY_UID, generate_study


@pytest.mark.dicom
def test_generator_writes_a_synthetic_study(tmp_path) -> None:
    paths = generate_study(tmp_path / "study")

    assert len(paths) == 3
    datasets = [dcmread(path) for path in paths]
    assert {str(dataset.StudyInstanceUID) for dataset in datasets} == {STUDY_UID}
    assert {str(dataset.PatientID) for dataset in datasets} == {"SYNTHETIC-001"}
    assert all(dataset.file_meta.TransferSyntaxUID.is_little_endian for dataset in datasets)
