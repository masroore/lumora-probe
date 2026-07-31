"""Pure lexical DICOM UID and AE-title inspection primitives."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

UIDReason = Literal["missing", "invalid"]
AETitleReason = Literal["non_ascii", "invalid_length"]

_UID_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+)+$")
_MAX_UID_LENGTH = 64
_MIN_AE_TITLE_BYTES = 1
_MAX_AE_TITLE_BYTES = 16


@dataclass(frozen=True, slots=True)
class UidInspection:
    """Result of inspecting one scalar UID value."""

    value: str | None
    reason: UIDReason | None


@dataclass(frozen=True, slots=True)
class AETitleInspection:
    """Result of inspecting one AE title's ASCII encoding and byte length."""

    encoded: bytes | None
    reason: AETitleReason | None


def inspect_uid(value: object) -> UidInspection:
    """Normalize a scalar UID and report missing or invalid lexical input.

    Product adapters perform product-specific unwrapping and multi-value handling
    before calling this function. Scalar values are stringified to preserve the
    Lite validator's existing behavior.
    """
    if value is None:
        return UidInspection(None, "missing")
    try:
        text = str(value)
    except (TypeError, ValueError):
        return UidInspection(None, "invalid")
    if not text:
        return UidInspection(None, "missing")
    components = text.split(".")
    if (
        len(text) > _MAX_UID_LENGTH
        or _UID_PATTERN.fullmatch(text) is None
        or any(len(component) > 1 and component.startswith("0") for component in components)
    ):
        return UidInspection(None, "invalid")
    return UidInspection(text, None)


def inspect_ae_title(value: str) -> AETitleInspection:
    """Inspect ASCII encoding and byte length without applying product policy.

    Whitespace and control-byte policy is deliberately excluded. Lite accepts
    those values; Lumora Probe applies its stricter policy in its domain object.
    """
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError:
        return AETitleInspection(None, "non_ascii")
    if not _MIN_AE_TITLE_BYTES <= len(encoded) <= _MAX_AE_TITLE_BYTES:
        return AETitleInspection(None, "invalid_length")
    return AETitleInspection(encoded, None)


__all__ = [
    "AETitleInspection",
    "AETitleReason",
    "UIDReason",
    "UidInspection",
    "inspect_ae_title",
    "inspect_uid",
]
