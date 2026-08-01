# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Tests for the byte-comparable golden capture harness."""

from __future__ import annotations

import pytest

from tests.golden.harness import GoldenFixtureMismatch, compare_bytes, golden_path


@pytest.mark.unit
def test_compare_bytes_accepts_identical_files(tmp_path) -> None:
    expected = tmp_path / "expected.lpcap"
    actual = tmp_path / "actual.lpcap"
    expected.write_bytes(b"capture")
    actual.write_bytes(b"capture")

    compare_bytes(expected, actual)


@pytest.mark.unit
def test_compare_bytes_reports_first_difference(tmp_path) -> None:
    expected = tmp_path / "expected.lpcap"
    actual = tmp_path / "actual.lpcap"
    expected.write_bytes(b"capture")
    actual.write_bytes(b"capturE")

    with pytest.raises(GoldenFixtureMismatch) as error:
        compare_bytes(expected, actual)

    assert error.value.mismatch.first_difference == 6


@pytest.mark.unit
def test_golden_path_rejects_traversal_and_wrong_extension(tmp_path) -> None:
    with pytest.raises(ValueError):
        golden_path(tmp_path, "../capture.lpcap")
    with pytest.raises(ValueError):
        golden_path(tmp_path, "capture.jsonl")
