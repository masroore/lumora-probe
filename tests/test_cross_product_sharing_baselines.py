# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Characterization tests for behavior preserved by neutral DICOM extraction."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumora_lite_common.config_validators import validate_ae_title
from lumora_lite_common.uids import (
    REASON_INVALID,
    REASON_MISSING,
    REASON_MULTI_VALUED,
    validate_uid,
)
from lumora_probe.associations.network import _status_code
from lumora_probe.shared.errors import DomainInvariantError
from lumora_probe.shared.value_objects import DICOMUID, AETitle
from sender_lite.sender import _read_status


def test_lite_uid_reason_contract_is_explicit() -> None:
    assert validate_uid(None) == (None, REASON_MISSING)
    assert validate_uid("") == (None, REASON_MISSING)
    assert validate_uid(["1.2.3", "1.2.4"]) == (None, REASON_MULTI_VALUED)
    assert validate_uid("not-a-uid") == (None, REASON_INVALID)
    assert validate_uid("1.2.840.10008.1.1") == ("1.2.840.10008.1.1", None)


def test_lite_ae_title_accepts_ascii_whitespace_and_control_values() -> None:
    validate_ae_title(" ", "ae")
    validate_ae_title("\x01", "ae")


def test_application_ae_title_retains_stricter_domain_policy() -> None:
    for value in ("", " ", "\x01", "é", "A" * 17):
        with pytest.raises(DomainInvariantError):
            AETitle(value)


def test_application_uid_retains_domain_exception_and_leading_zero_policy() -> None:
    DICOMUID("1.2.3")
    with pytest.raises(DomainInvariantError):
        DICOMUID("1.02.3")
    with pytest.raises(DomainInvariantError):
        DICOMUID("not-a-uid")


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (None, None),
        (SimpleNamespace(), None),
        (SimpleNamespace(Status=0x0000), 0x0000),
        (SimpleNamespace(Status="0x0000"), None),
        (SimpleNamespace(Status="malformed"), None),
    ],
)
def test_sender_status_reader_is_defensive(response: object, expected: int | None) -> None:
    assert _read_status(response) == expected


@pytest.mark.parametrize(
    "response",
    [None, SimpleNamespace(), SimpleNamespace(Status="malformed")],
)
def test_application_status_reader_retains_strict_failure(response: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _status_code(response)


def test_application_status_reader_accepts_numeric_status() -> None:
    assert _status_code(SimpleNamespace(Status=0x0122)) == 0x0122
    assert _status_code(SimpleNamespace(Status="290")) == 290
