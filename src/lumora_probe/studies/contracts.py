"""Public contracts for capture-backed study and image projections."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
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
