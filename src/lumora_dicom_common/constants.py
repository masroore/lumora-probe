"""Universal DICOM endpoint constants shared by product adapters."""

from __future__ import annotations

DEFAULT_DICOM_PORT = 11112
DEFAULT_DICOM_MAX_PDU = 16_382
DICOM_SUCCESS_STATUS = 0x0000

__all__ = ["DEFAULT_DICOM_MAX_PDU", "DEFAULT_DICOM_PORT", "DICOM_SUCCESS_STATUS"]
