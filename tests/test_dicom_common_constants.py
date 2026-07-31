"""Tests for neutral DICOM constants."""

from __future__ import annotations

from lumora_dicom_common.constants import (
    DEFAULT_DICOM_MAX_PDU,
    DEFAULT_DICOM_PORT,
    DICOM_SUCCESS_STATUS,
)


def test_dicom_constants_match_existing_product_defaults() -> None:
    assert DEFAULT_DICOM_PORT == 11112
    assert DEFAULT_DICOM_MAX_PDU == 16_382
    assert DICOM_SUCCESS_STATUS == 0x0000
