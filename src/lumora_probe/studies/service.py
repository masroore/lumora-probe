"""Server-side DICOM frame decoding, evidence, caching, and prefetch."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import Executor
from io import BytesIO
from typing import Any

import numpy as np
from pydicom import dcmread
from pydicom.dataset import Dataset

from lumora_probe.shared.events import EventEnvelope, EventOrigin

from .contracts import (
    DecodedFrame,
    DecodedFrameMetadata,
    DecodeFailureKind,
    DicomObjectSource,
    ImageDecodeClock,
    ImageDecodeEventPublisher,
    ImageDecodeIdGenerator,
)
from .domain import DecodeError, failure


class LRUFrameCache:
    """Bounded server-side frame cache with deterministic LRU eviction."""

    def __init__(self, max_items: int = 128) -> None:
        if type(max_items) is not int or max_items < 1:
            raise ValueError("max_items must be a positive integer")
        self.max_items = max_items
        self._items: OrderedDict[tuple[str, int], DecodedFrame] = OrderedDict()

    def get(self, key: tuple[str, int]) -> DecodedFrame | None:
        value = self._items.get(key)
        if value is None:
            return None
        self._items.move_to_end(key)
        return value

    def put(self, key: tuple[str, int], value: DecodedFrame) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self.max_items:
            self._items.popitem(last=False)

    def __len__(self) -> int:
        return len(self._items)


class PydicomFrameDecoder:
    """Decode DICOM pixels synchronously; callers must invoke it in an executor."""

    def __call__(self, source: DicomObjectSource, frame_number: int) -> DecodedFrame:
        if frame_number < 0 or frame_number >= source.frame_count:
            raise failure(
                DecodeFailureKind.FRAME_OUT_OF_RANGE,
                f"Frame {frame_number} is outside the available frame range.",
                "Request a frame number from zero through frame_count - 1.",
                frame_number=frame_number,
                frame_count=source.frame_count,
            )
        try:
            dataset = dcmread(BytesIO(source.raw_bytes), force=False)
        except Exception as exc:
            raise failure(
                DecodeFailureKind.INVALID_DICOM,
                "The object is not a readable DICOM Part 10 dataset.",
                "Verify the capture object digest and inspect the source transfer.",
                error=str(exc),
            ) from exc

        try:
            pixel_array = dataset.pixel_array
        except NotImplementedError as exc:
            raise failure(
                DecodeFailureKind.UNSUPPORTED_TRANSFER_SYNTAX,
                "The server has no decoder for this transfer syntax.",
                "Install a codec for the transfer syntax or capture an uncompressed representation.",
                transfer_syntax=_transfer_syntax(dataset),
                error=str(exc),
            ) from exc
        except Exception as exc:
            raise failure(
                DecodeFailureKind.PIXEL_DATA_BROKEN,
                "DICOM metadata was readable, but pixel data could not be decoded.",
                "Inspect pixel data length, samples-per-pixel, and transfer syntax in the source capture.",
                transfer_syntax=_transfer_syntax(dataset),
                error=str(exc),
            ) from exc

        array = _select_frame(np.asarray(pixel_array), dataset, frame_number)
        normalized = _normalize_grayscale(array)
        rows, columns = normalized.shape
        slope = _number(dataset.get("RescaleSlope", 1.0), 1.0)
        intercept = _number(dataset.get("RescaleIntercept", 0.0), 0.0)
        center = _number(
            dataset.get("WindowCenter", _suggested_center(normalized)),
            _suggested_center(normalized),
        )
        width = _number(
            dataset.get("WindowWidth", _suggested_width(normalized)), _suggested_width(normalized)
        )
        metadata = DecodedFrameMetadata(
            rows=rows,
            columns=columns,
            frame_number=frame_number,
            frame_count=source.frame_count,
            bits_allocated=int(dataset.get("BitsAllocated", 16)),
            pixel_representation=int(dataset.get("PixelRepresentation", 0)),
            rescale_slope=slope,
            rescale_intercept=intercept,
            suggested_window_center=center,
            suggested_window_width=max(width, 1.0),
            photometric_interpretation=str(dataset.get("PhotometricInterpretation", "UNKNOWN")),
            transfer_syntax_uid=_transfer_syntax(dataset),
        )
        return DecodedFrame(
            pixels=normalized.astype("<u2", copy=False).tobytes(), metadata=metadata, duration_ns=0
        )


class DecodeService:
    """Async decode facade; all pydicom and numpy work runs off the event loop."""

    def __init__(
        self,
        *,
        decoder: Callable[[DicomObjectSource, int], DecodedFrame] | None = None,
        cache: LRUFrameCache | None = None,
        executor: Executor | None = None,
        clock: ImageDecodeClock,
        event_publisher: ImageDecodeEventPublisher | None = None,
        id_generator: ImageDecodeIdGenerator | None = None,
    ) -> None:
        self.decoder = decoder or PydicomFrameDecoder()
        self.cache = cache or LRUFrameCache()
        self.executor = executor
        self.clock = clock
        self.event_publisher = event_publisher
        self.id_generator = id_generator
        self._prefetch_tasks: set[asyncio.Task[None]] = set()

    async def decode(
        self,
        source: DicomObjectSource,
        *,
        frame_number: int = 0,
        prefetch: bool = True,
    ) -> DecodedFrame:
        key = (source.object_digest, frame_number)
        cached = self.cache.get(key)
        if cached is not None:
            result = DecodedFrame(
                pixels=cached.pixels,
                metadata=DecodedFrameMetadata(**{**cached.metadata.as_dict(), "cache_hit": True}),
                duration_ns=0,
            )
        else:
            started = self.clock.monotonic_ns()
            loop = asyncio.get_running_loop()
            try:
                decoded = await loop.run_in_executor(
                    self.executor, self.decoder, source, frame_number
                )
            except DecodeError:
                raise
            except Exception as exc:
                raise failure(
                    DecodeFailureKind.PIXEL_DATA_BROKEN,
                    "The server decoder failed while processing pixel data.",
                    "Inspect the decoder error and source capture object.",
                    error=str(exc),
                ) from exc
            duration_ns = max(0, self.clock.monotonic_ns() - started)
            result = DecodedFrame(
                pixels=decoded.pixels,
                metadata=DecodedFrameMetadata(**{**decoded.metadata.as_dict(), "cache_hit": False}),
                duration_ns=duration_ns,
            )
            self.cache.put(key, result)
            await self._publish_decoded(source, result)
        if prefetch and source.frame_count > 1:
            self._schedule_prefetch(source, frame_number)
        return result

    async def drain_prefetch(self) -> None:
        """Wait for currently scheduled prefetch tasks in deterministic tests or shutdown."""
        if self._prefetch_tasks:
            await asyncio.gather(*tuple(self._prefetch_tasks))

    def _schedule_prefetch(self, source: DicomObjectSource, frame_number: int) -> None:
        for candidate in range(max(0, frame_number - 2), min(source.frame_count, frame_number + 3)):
            if (
                candidate == frame_number
                or self.cache.get((source.object_digest, candidate)) is not None
            ):
                continue
            task = asyncio.create_task(self.decode(source, frame_number=candidate, prefetch=False))
            self._prefetch_tasks.add(task)
            task.add_done_callback(self._prefetch_tasks.discard)

    async def _publish_decoded(self, source: DicomObjectSource, result: DecodedFrame) -> None:
        if self.event_publisher is None:
            return
        if self.id_generator is None:
            raise ValueError("ImageDecoded evidence requires an injected ID generator")
        event_id = self.id_generator.new_id()
        event = EventEnvelope.create(
            event_name="ImageDecoded",
            event_version=1,
            correlation_id=event_id,
            aggregate_type="Instance",
            aggregate_id=source.instance_id or source.object_digest,
            producer="studies.decode",
            payload={
                "object_digest": source.object_digest,
                "frame_number": result.metadata.frame_number,
                "duration_ns": result.duration_ns,
                "rows": result.metadata.rows,
                "columns": result.metadata.columns,
                "cache_hit": result.metadata.cache_hit,
                "decode_failure": None,
            },
            origin=EventOrigin.OBSERVED,
            clock=self.clock,
            id_generator=self.id_generator,
        )
        await self.event_publisher.publish(event, capture_id=source.capture_id)


def _select_frame(array: np.ndarray, dataset: Dataset, frame_number: int) -> np.ndarray:
    samples = int(dataset.get("SamplesPerPixel", 1))
    if array.ndim == 2:
        if frame_number != 0:
            raise failure(
                DecodeFailureKind.FRAME_OUT_OF_RANGE,
                f"Frame {frame_number} is outside the single-frame object.",
                "Request frame 0 for this object.",
                frame_number=frame_number,
            )
        return array
    if samples > 1 and array.ndim == 3:
        if frame_number != 0:
            raise failure(
                DecodeFailureKind.FRAME_OUT_OF_RANGE,
                f"Frame {frame_number} is outside the single-frame color object.",
                "Request frame 0 for this object.",
                frame_number=frame_number,
            )
        return _to_grayscale(array)
    if array.ndim >= 3:
        if frame_number >= array.shape[0]:
            raise failure(
                DecodeFailureKind.FRAME_OUT_OF_RANGE,
                f"Frame {frame_number} is outside the decoded pixel array.",
                "Request an available frame number.",
                frame_number=frame_number,
                decoded_frame_count=int(array.shape[0]),
            )
        selected = array[frame_number]
        return _to_grayscale(selected) if samples > 1 else selected
    raise failure(
        DecodeFailureKind.PIXEL_DATA_BROKEN,
        "The decoded pixel array has an unsupported shape.",
        "Inspect SamplesPerPixel and NumberOfFrames in the source dataset.",
        shape=tuple(int(value) for value in array.shape),
    )


def _to_grayscale(array: np.ndarray) -> np.ndarray:
    if array.ndim < 3 or array.shape[-1] < 3:
        return array
    rgb = array[..., :3].astype(np.float64)
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def _normalize_grayscale(array: np.ndarray) -> np.ndarray:
    values = np.asarray(array)
    if values.ndim != 2:
        raise failure(
            DecodeFailureKind.PIXEL_DATA_BROKEN,
            "The decoder did not produce a two-dimensional grayscale frame.",
            "Inspect the source samples-per-pixel and frame layout.",
            shape=tuple(int(value) for value in values.shape),
        )
    if np.issubdtype(values.dtype, np.unsignedinteger):
        info = np.iinfo(values.dtype)
        scaled = values.astype(np.float64) * (65535.0 / info.max)
    elif np.issubdtype(values.dtype, np.signedinteger):
        info = np.iinfo(values.dtype)
        scaled = (values.astype(np.float64) - info.min) * (65535.0 / (info.max - info.min))
    else:
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            raise failure(
                DecodeFailureKind.PIXEL_DATA_BROKEN,
                "Pixel data contains no finite values.",
                "Inspect the encoded pixel payload for corruption.",
            )
        minimum = float(finite.min())
        maximum = float(finite.max())
        scaled = (
            np.zeros(values.shape, dtype=np.float64)
            if maximum == minimum
            else ((values.astype(np.float64) - minimum) * (65535.0 / (maximum - minimum)))
        )
    return np.clip(scaled, 0, 65535).astype(np.uint16)


def _transfer_syntax(dataset: Dataset) -> str:
    return str(getattr(dataset.file_meta, "TransferSyntaxUID", "unknown"))


def _number(value: Any, default: float) -> float:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _suggested_center(array: np.ndarray) -> float:
    return float(array.min()) + (float(array.max()) - float(array.min())) / 2.0


def _suggested_width(array: np.ndarray) -> float:
    return max(1.0, float(array.max()) - float(array.min()))


__all__: tuple[str, ...] = ()
