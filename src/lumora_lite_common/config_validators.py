"""Shared config leaf validators for the Lumora Lite tools.

These are the small, pure checks that both tools' ``Config`` validation
duplicated verbatim: port range, max-PDU range, log-format membership, and AE
title encoding/length. Each raises ``ValueError`` on failure with the same
message wording the tools already used, so swapping the inline checks for these
helpers changes no observable behaviour. Plain functions, no state — see
ADR-0028.
"""

from __future__ import annotations

from lumora_dicom_common.identifiers import inspect_ae_title

MIN_PORT = 1
MAX_PORT = 65535
MIN_MAX_PDU = 1
MAX_MAX_PDU = 16_777_215
MIN_AE_BYTES = 1
MAX_AE_BYTES = 16
_VALID_LOG_FORMATS = frozenset({"text", "json"})


def validate_port(port: int) -> None:
    """Raise ``ValueError`` unless ``port`` is in 1..65535."""
    if not MIN_PORT <= port <= MAX_PORT:
        raise ValueError("port must be between 1 and 65535")


def validate_max_pdu(max_pdu: int) -> None:
    """Raise ``ValueError`` unless ``max_pdu`` is in 1..16777215."""
    if not MIN_MAX_PDU <= max_pdu <= MAX_MAX_PDU:
        raise ValueError("max-pdu must be between 1 and 16777215")


def validate_log_format(log_format: str) -> None:
    """Raise ``ValueError`` unless ``log_format`` is ``text`` or ``json``."""
    if log_format not in _VALID_LOG_FORMATS:
        raise ValueError("format must be text or json")


def validate_ae_title(value: str, name: str) -> None:
    """Raise ``ValueError`` unless ``value`` is 1..16 ASCII characters.

    ``name`` is used in the error message and is expected to be the field's
    human label (for example ``"AE title"`` or ``"calling-ae"``), matching the
    wording each tool already produced.
    """
    inspection = inspect_ae_title(value)
    if inspection.reason == "non_ascii":
        raise ValueError(f"{name} must contain only ASCII characters")
    if inspection.reason == "invalid_length":
        raise ValueError(f"{name} must be 1 to 16 ASCII characters")
