# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Tests for the shared config leaf validators."""

from __future__ import annotations

import pytest

from lumora_lite_common.config_validators import (
    MAX_AE_BYTES,
    MAX_MAX_PDU,
    MAX_PORT,
    validate_ae_title,
    validate_log_format,
    validate_max_pdu,
    validate_port,
)


def test_validate_port_accepts_boundaries() -> None:
    validate_port(1)
    validate_port(MAX_PORT)
    validate_port(11112)


@pytest.mark.parametrize("bad", [0, -1, MAX_PORT + 1, 65536])
def test_validate_port_rejects_out_of_range(bad: int) -> None:
    with pytest.raises(ValueError, match="port"):
        validate_port(bad)


def test_validate_max_pdu_accepts_boundaries() -> None:
    validate_max_pdu(1)
    validate_max_pdu(MAX_MAX_PDU)
    validate_max_pdu(16382)


@pytest.mark.parametrize("bad", [0, MAX_MAX_PDU + 1])
def test_validate_max_pdu_rejects_out_of_range(bad: int) -> None:
    with pytest.raises(ValueError, match="max-pdu"):
        validate_max_pdu(bad)


def test_validate_log_format_accepts_known() -> None:
    validate_log_format("text")
    validate_log_format("json")


def test_validate_log_format_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="format"):
        validate_log_format("xml")


def test_validate_ae_title_accepts_ascii() -> None:
    validate_ae_title("A", "ae")
    validate_ae_title("A" * MAX_AE_BYTES, "ae")
    validate_ae_title("PROBE_LITE", "ae")


def test_validate_ae_title_rejects_non_ascii() -> None:
    with pytest.raises(ValueError, match="ASCII"):
        validate_ae_title("ÜNICODE", "ae")


def test_validate_ae_title_rejects_empty() -> None:
    with pytest.raises(ValueError, match="1 to 16"):
        validate_ae_title("", "ae")


def test_validate_ae_title_rejects_too_long() -> None:
    with pytest.raises(ValueError, match="1 to 16"):
        validate_ae_title("X" * (MAX_AE_BYTES + 1), "ae")


def test_validate_ae_title_uses_name_in_message() -> None:
    with pytest.raises(ValueError, match="calling-ae"):
        validate_ae_title("", "calling-ae")
