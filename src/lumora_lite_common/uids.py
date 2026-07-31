"""DICOM UID validation for the Lumora Lite tools.

Both tools enforce the same DICOM rule (UI value: dotted-decimal digits, ≤64
chars) but previously did so with two implementations — Sender used pydicom's
``UID``; Probe used a regex. This module consolidates them behind plain
functions:

- :func:`validate_uid` returns the normalised UID plus a generic failure
  reason. It is the primary entry point.
- :func:`is_valid_uid` is the boolean predicate.
- :func:`safe_uid` returns the UID or raises ``ValueError``.

pydicom is used when importable because it provides the most faithful validity
check (``UID.is_valid``). When pydicom is absent, a regex enforces the same
shape and length, so importing this module never hard-requires pydicom. See
ADR-0028.
"""

from __future__ import annotations

from typing import Literal

from lumora_dicom_common.identifiers import inspect_uid

#: Stable, generic reason categories for :func:`validate_uid`. Callers map these
#: to their own reason codes (Sender) or treat any failure uniformly (Probe).
REASON_MISSING = "missing"
REASON_MULTI_VALUED = "multi_valued"
REASON_INVALID = "invalid"

UidReason = Literal["missing", "multi_valued", "invalid"]

_MULTI_VALUE_TYPE_NAME = "MultiValue"


def validate_uid(value: object) -> tuple[str | None, UidReason | None]:
    """Validate a UID-valued attribute while preserving Lite reason categories."""
    if value is None:
        return None, REASON_MISSING
    if hasattr(value, "value"):
        value = value.value
    if isinstance(value, list) or type(value).__name__ == _MULTI_VALUE_TYPE_NAME:
        return None, REASON_MULTI_VALUED

    result = inspect_uid(value)
    return result.value, result.reason


def is_valid_uid(value: object) -> bool:
    """Return ``True`` iff ``value`` is a valid DICOM UID."""
    return validate_uid(value)[1] is None


def safe_uid(value: str) -> str:
    """Return the normalised UID, or raise ``ValueError`` if invalid."""
    uid, reason = validate_uid(value)
    if uid is None:
        raise ValueError(f"invalid DICOM UID: {value!r} ({reason})")
    return uid
