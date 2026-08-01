# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Public contracts for capture-backed study and image projections."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol


class DecodeFailureKind(StrEnum):
    """Explainable server-side decode failure categories."""

    INVALID_DICOM = "invalid-dicom"
    UNSUPPORTED_TRANSFER_SYNTAX = "unsupported-transfer-syntax"
    PIXEL_DATA_BROKEN = "pixel-data-broken"
    FRAME_OUT_OF_RANGE = "frame-out-of-range"
    BROWSER_RENDERER_UNSUPPORTED = "browser-renderer-unsupported"


@dataclass(frozen=True, slots=True)
class DicomObjectSource:
    """Capture-owned DICOM bytes supplied through the application composition seam."""

    object_digest: str
    raw_bytes: bytes
    capture_id: str | None = None
    instance_id: str | None = None
    frame_count: int = 1

    def __post_init__(self) -> None:
        if not self.object_digest.strip():
            raise ValueError("object_digest must not be empty")
        if not self.raw_bytes:
            raise ValueError("raw_bytes must not be empty")
        if self.frame_count < 1:
            raise ValueError("frame_count must be positive")
        object.__setattr__(self, "raw_bytes", bytes(self.raw_bytes))


@dataclass(frozen=True, slots=True)
class DecodedFrameMetadata:
    """JSON sidecar metadata for one normalized frame."""

    rows: int
    columns: int
    frame_number: int
    frame_count: int
    bits_allocated: int
    pixel_representation: int
    rescale_slope: float
    rescale_intercept: float
    suggested_window_center: float
    suggested_window_width: float
    photometric_interpretation: str
    transfer_syntax_uid: str
    cache_hit: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return the stable JSON sidecar representation."""
        return {
            "rows": self.rows,
            "columns": self.columns,
            "frame_number": self.frame_number,
            "frame_count": self.frame_count,
            "bits_allocated": self.bits_allocated,
            "pixel_representation": self.pixel_representation,
            "rescale_slope": self.rescale_slope,
            "rescale_intercept": self.rescale_intercept,
            "suggested_window_center": self.suggested_window_center,
            "suggested_window_width": self.suggested_window_width,
            "photometric_interpretation": self.photometric_interpretation,
            "transfer_syntax_uid": self.transfer_syntax_uid,
            "cache_hit": self.cache_hit,
        }


@dataclass(frozen=True, slots=True)
class DecodedFrame:
    """One normalized little-endian uint16 frame and its sidecar."""

    pixels: bytes
    metadata: DecodedFrameMetadata
    duration_ns: int


@dataclass(frozen=True, slots=True)
class DecodeFailure:
    """Structured explanation returned when a frame cannot be decoded."""

    kind: DecodeFailureKind
    message: str
    remediation: str
    context: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class InstanceRetention:
    """Retention and promotion metadata for one capture-backed instance."""

    source: str = "capture"
    expires_at: datetime | None = None
    promotion_start: datetime | None = None
    promotion_end: datetime | None = None
    aggregate_id: str | None = None

    @classmethod
    def permanent(cls) -> InstanceRetention:
        """Return retention metadata for an already materialized capture object."""
        return cls()

    @property
    def state(self) -> str:
        """Return the user-facing retention state."""
        if self.source == "ring-buffer":
            return "retained" if self.expires_at is not None else "expiring"
        return "permanent"

    @property
    def promotable(self) -> bool:
        """Return whether the browser can offer inline ring-buffer promotion."""
        return (
            self.source == "ring-buffer"
            and self.promotion_start is not None
            and self.promotion_end is not None
        )

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-compatible retention metadata for browser clients."""
        return {
            "source": self.source,
            "state": self.state,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "promotion_start": (self.promotion_start.isoformat() if self.promotion_start else None),
            "promotion_end": self.promotion_end.isoformat() if self.promotion_end else None,
            "aggregate_id": self.aggregate_id,
            "promotable": self.promotable,
        }


@dataclass(frozen=True, slots=True)
class InstanceProvenance:
    """Capture provenance for one SOP Instance UID in the Study Browser."""

    sop_instance_uid: str
    capture_ids: tuple[str, ...]
    object_digests: tuple[str, ...]
    retention: InstanceRetention = field(default_factory=InstanceRetention.permanent)

    @property
    def present_in_capture_count(self) -> int:
        """Return the number of captures containing this instance identity."""
        return len(self.capture_ids)

    @property
    def duplicate(self) -> bool:
        """Return whether one SOP Instance UID has differing bytes."""
        return len(self.object_digests) > 1

    def as_dict(self) -> dict[str, Any]:
        """Return the stable browser representation for this instance."""
        return {
            "sop_instance_uid": self.sop_instance_uid,
            "capture_ids": list(self.capture_ids),
            "object_digests": list(self.object_digests),
            "present_in_capture_count": self.present_in_capture_count,
            "duplicate": self.duplicate,
            "retention": self.retention.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class DuplicateInstanceFinding:
    """Deterministic finding data for conflicting SOP Instance bytes."""

    sop_instance_uid: str
    object_digests: tuple[str, ...]
    capture_ids: tuple[str, ...]
    kind: str = "duplicate-sop-instance-uid"


@dataclass(frozen=True, slots=True)
class MetadataTag:
    """One searchable DICOM metadata element exposed by the inspector."""

    tag: str
    keyword: str
    vr: str
    value: str
    private: bool

    def as_dict(self) -> dict[str, Any]:
        """Return the stable JSON representation used by the inspector."""
        return {
            "tag": self.tag,
            "keyword": self.keyword,
            "vr": self.vr,
            "value": self.value,
            "private": self.private,
        }


@dataclass(frozen=True, slots=True)
class MetadataInspection:
    """Metadata inspector result for one capture-owned DICOM object."""

    instance_id: str
    tags: tuple[MetadataTag, ...]
    raw_dump: str

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-compatible inspector data."""
        return {
            "instance_id": self.instance_id,
            "tags": [tag.as_dict() for tag in self.tags],
            "raw_dump": self.raw_dump,
        }


@dataclass(frozen=True, slots=True)
class FolderImportObject:
    """Verified object discovered during offline folder import."""

    path: str
    object_digest: str
    study_uid: str
    series_uid: str
    sop_instance_uid: str
    raw_bytes: bytes


@dataclass(frozen=True, slots=True)
class FolderImportResult:
    """Synthetic object-fidelity capture request produced by folder import."""

    capture_id: str
    fidelity: str
    objects: tuple[FolderImportObject, ...]


class SyntheticCaptureWriter(Protocol):
    """Application seam that materializes an offline folder as a capture."""

    async def write_synthetic_capture(
        self, objects: tuple[FolderImportObject, ...], *, fidelity: str
    ) -> str: ...


class ImageDecodeEventPublisher(Protocol):
    """Minimal event bus contract used by decode evidence."""

    async def publish(self, event: Any, *, capture_id: str | None = None) -> Any: ...


class ImageDecodeClock(Protocol):
    """Injected wall and monotonic clock contract."""

    def now(self) -> datetime: ...

    def monotonic_ns(self) -> int: ...


class ImageDecodeIdGenerator(Protocol):
    """Injected UUIDv7 generator for decode event identities."""

    def new_id(self) -> str: ...


FrameDecoder = Callable[[DicomObjectSource, int], DecodedFrame]


__all__: tuple[str, ...] = ()
