# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Tests for the shared DICOM UID validation helpers."""

from __future__ import annotations

import pytest

from lumora_lite_common.uids import (
    REASON_INVALID,
    REASON_MISSING,
    REASON_MULTI_VALUED,
    is_valid_uid,
    safe_uid,
    validate_uid,
)


def test_validate_uid_accepts_well_formed() -> None:
    assert validate_uid("1.2.840.10008.5.1.4.1.1.2") == ("1.2.840.10008.5.1.4.1.1.2", None)


def test_validate_uid_missing_for_none() -> None:
    assert validate_uid(None) == (None, REASON_MISSING)


def test_validate_uid_missing_for_empty() -> None:
    assert validate_uid("") == (None, REASON_MISSING)


def test_validate_uid_multi_valued_for_list() -> None:
    assert validate_uid(["1.2.3", "1.2.4"]) == (None, REASON_MULTI_VALUED)


def test_validate_uid_unwraps_pydicom_datavalue() -> None:
    class _Element:
        value = "1.2.3"

    assert validate_uid(_Element()) == ("1.2.3", None)


def test_validate_uid_invalid_for_bad_shape() -> None:
    assert validate_uid("not-a-uid") == (None, REASON_INVALID)


def test_validate_uid_invalid_for_too_long() -> None:
    # 65 chars, well-shaped digits -> invalid by length only
    long_uid = "1." + ".".join("1" for _ in range(63))
    assert len(long_uid) > 64
    assert validate_uid(long_uid)[1] == REASON_INVALID


def test_is_valid_uid_predicate() -> None:
    assert is_valid_uid("1.2.3") is True
    assert is_valid_uid("bad") is False
    assert is_valid_uid(None) is False


def test_safe_uid_returns_uid() -> None:
    assert safe_uid("1.2.3") == "1.2.3"


def test_safe_uid_raises_on_invalid() -> None:
    with pytest.raises(ValueError, match="invalid DICOM UID"):
        safe_uid("nope")
