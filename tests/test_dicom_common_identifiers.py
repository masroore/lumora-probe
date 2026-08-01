# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Tests for neutral DICOM identifier mechanics."""

from __future__ import annotations

import pytest

from lumora_dicom_common.identifiers import inspect_ae_title, inspect_uid


@pytest.mark.parametrize("value", ["1.2.840.10008.1.1", "1.2.3", 1.2])
def test_inspect_uid_accepts_scalar_dotted_decimal_values(value: object) -> None:
    result = inspect_uid(value)
    assert result.reason is None
    assert result.value is not None


@pytest.mark.parametrize("value", [None, ""])
def test_inspect_uid_reports_missing(value: object) -> None:
    result = inspect_uid(value)
    assert result.value is None
    assert result.reason == "missing"


@pytest.mark.parametrize("value", ["not-a-uid", "1.02.3", "01.2", "1..2", "1."])
def test_inspect_uid_rejects_invalid_shape_or_leading_zero(value: str) -> None:
    result = inspect_uid(value)
    assert result.value is None
    assert result.reason == "invalid"


def test_inspect_uid_rejects_values_over_64_characters() -> None:
    value = "1." + ".".join("1" for _ in range(63))
    assert len(value) > 64
    result = inspect_uid(value)
    assert result.value is None
    assert result.reason == "invalid"


@pytest.mark.parametrize("value", ["PROBE", " ", "\x01", "A" * 16])
def test_inspect_ae_title_only_checks_ascii_bytes_and_length(value: str) -> None:
    result = inspect_ae_title(value)
    assert result.reason is None
    assert result.encoded == value.encode("ascii")


@pytest.mark.parametrize("value", ["", "A" * 17])
def test_inspect_ae_title_rejects_invalid_length(value: str) -> None:
    result = inspect_ae_title(value)
    assert result.encoded is None
    assert result.reason == "invalid_length"


def test_inspect_ae_title_rejects_non_ascii() -> None:
    result = inspect_ae_title("ÜNICODE")
    assert result.encoded is None
    assert result.reason == "non_ascii"
