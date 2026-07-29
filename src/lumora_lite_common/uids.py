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

import re
from typing import Literal

#: Stable, generic reason categories for :func:`validate_uid`. Callers map these
#: to their own reason codes (Sender) or treat any failure uniformly (Probe).
REASON_MISSING = "missing"
REASON_MULTI_VALUED = "multi_valued"
REASON_INVALID = "invalid"

UidReason = Literal["missing", "multi_valued", "invalid"]

_MAX_UID_LENGTH = 64
# DICOM UI VR shape: numeric org root plus one or more numeric suffix segments.
_UID_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+)+$")
_pydicom_uid = None


def _load_uid():
    """Return pydicom's ``UID`` class, or ``None`` if pydicom is unavailable."""
    global _pydicom_uid
    if _pydicom_uid is None:
        try:
            from pydicom.uid import UID as _pydicom_uid
        except ImportError:
            _pydicom_uid = False
    return _pydicom_uid or None


def validate_uid(value: object) -> tuple[str | None, UidReason | None]:
    """Validate a UID-valued attribute.

    Accepts raw strings, pydicom ``DataElement`` (unwraps ``.value``), and
    detects pydicom ``MultiValue``. Returns ``(uid_str, None)`` on success or
    ``(None, reason)`` on failure, where ``reason`` is one of the
    :data:`REASON_*` categories.
    """
    if value is None:
        return None, REASON_MISSING
    # pydicom DataElement: unwrap .value
    if hasattr(value, "value"):
        value = value.value
    # Detect multi-valued (pydicom MultiValue)
    if isinstance(value, list) or type(value).__name__ == "MultiValue":
        return None, REASON_MULTI_VALUED
    try:
        text = str(value)
    except (TypeError, ValueError):
        return None, REASON_INVALID
    if not text:
        return None, REASON_MISSING

    uid_cls = _load_uid()
    if uid_cls is not None:
        try:
            uid = uid_cls(text)
        except (TypeError, ValueError):
            return None, REASON_INVALID
        if not uid.is_valid or len(uid) > _MAX_UID_LENGTH:
            return None, REASON_INVALID
        return str(uid), None

    # Regex fallback (pydicom unavailable): same shape + length rule.
    if len(text) > _MAX_UID_LENGTH or not _UID_PATTERN.fullmatch(text):
        return None, REASON_INVALID
    return text, None


def is_valid_uid(value: object) -> bool:
    """Return ``True`` iff ``value`` is a valid DICOM UID."""
    return validate_uid(value)[1] is None


def safe_uid(value: str) -> str:
    """Return the normalised UID, or raise ``ValueError`` if invalid."""
    uid, reason = validate_uid(value)
    if uid is None:
        raise ValueError(f"invalid DICOM UID: {value!r} ({reason})")
    return uid
