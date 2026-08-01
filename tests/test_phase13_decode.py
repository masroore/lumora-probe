"""Phase 13 server-side decode pipeline tests."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from io import BytesIO

import numpy as np
import pytest
from pydicom import dcmwrite
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian

from lumora_probe.shared.events import EventEnvelope
from lumora_probe.studies.contracts import DecodeFailureKind, DicomObjectSource
from lumora_probe.studies.domain import DecodeError
from lumora_probe.studies.service import DecodeService, LRUFrameCache, PydicomFrameDecoder
from tests.doubles.clock import ControllableClock
from tests.doubles.ids import SeededIdGenerator


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []

    async def publish(
        self, event: EventEnvelope, *, capture_id: str | None = None
    ) -> EventEnvelope:
        self.events.append(event)
        return event


def make_dicom(*, frames: int = 1) -> bytes:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = CTImageStorage
    file_meta.MediaStorageSOPInstanceUID = "1.2.826.0.1.3680043.10.543.13.1"
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dataset = Dataset()
    dataset.file_meta = file_meta
    dataset.SOPClassUID = CTImageStorage
    dataset.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    dataset.StudyInstanceUID = "1.2.826.0.1.3680043.10.543.13.2"
    dataset.SeriesInstanceUID = "1.2.826.0.1.3680043.10.543.13.3"
    dataset.Rows = 2
    dataset.Columns = 2
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.BitsAllocated = 16
    dataset.BitsStored = 16
    dataset.HighBit = 15
    dataset.PixelRepresentation = 0
    dataset.NumberOfFrames = str(frames)
    pixels = np.stack(
        [np.array([[0, 1000], [2000, 3000]], dtype="<u2") + index for index in range(frames)]
    )
    dataset.PixelData = pixels.tobytes()
    output = BytesIO()
    dcmwrite(output, dataset, enforce_file_format=True)
    return output.getvalue()


def source(*, frames: int = 1) -> DicomObjectSource:
    return DicomObjectSource(
        object_digest="a" * 64,
        raw_bytes=make_dicom(frames=frames),
        capture_id="018f0d4e-7b6a-7000-8000-000000000701",
        instance_id="1.2.826.0.1.3680043.10.543.13.1",
        frame_count=frames,
    )


def clock() -> ControllableClock:
    return ControllableClock(datetime(2026, 7, 30, tzinfo=UTC))


@pytest.mark.component
@pytest.mark.asyncio
async def test_decode_normalizes_frame_and_publishes_duration_evidence() -> None:
    publisher = RecordingPublisher()
    service = DecodeService(
        clock=clock(),
        event_publisher=publisher,
        id_generator=SeededIdGenerator(
            [
                "018f0d4e-7b6a-7000-8000-000000000702",
                "018f0d4e-7b6a-7000-8000-000000000703",
            ]
        ),
    )

    result = await service.decode(source())

    assert len(result.pixels) == 2 * 2 * 2
    assert result.metadata.rows == 2
    assert result.metadata.columns == 2
    assert result.metadata.photometric_interpretation == "MONOCHROME2"
    assert result.metadata.cache_hit is False
    assert result.duration_ns >= 0
    assert len(publisher.events) == 1
    assert publisher.events[0].event_name == "ImageDecoded"
    assert publisher.events[0].origin.value == "observed"
    assert publisher.events[0].payload["duration_ns"] == result.duration_ns


@pytest.mark.component
@pytest.mark.asyncio
async def test_decode_runs_in_executor_and_cache_avoids_second_decode() -> None:
    calls: list[int] = []
    thread_ids: list[int] = []
    loop_thread = threading.get_ident()

    def decoder(object_source: DicomObjectSource, frame_number: int):
        calls.append(frame_number)
        thread_ids.append(threading.get_ident())
        return PydicomFrameDecoder()(object_source, frame_number)

    service = DecodeService(decoder=decoder, cache=LRUFrameCache(2), clock=clock())
    first = await service.decode(source())
    second = await service.decode(source())

    assert first.metadata.cache_hit is False
    assert second.metadata.cache_hit is True
    assert calls == [0]
    assert thread_ids[0] != loop_thread


@pytest.mark.component
@pytest.mark.asyncio
async def test_decode_prefetches_two_frames_each_side_without_hard_cache_cap() -> None:
    service = DecodeService(cache=LRUFrameCache(8), clock=clock())
    await service.decode(source(frames=5), frame_number=2)
    await service.drain_prefetch()

    assert len(service.cache) == 5


@pytest.mark.unit
def test_invalid_dicom_explains_failure_category() -> None:
    with pytest.raises(DecodeError) as error:
        PydicomFrameDecoder()(DicomObjectSource("b" * 64, b"not-dicom"), 0)

    assert error.value.failure.kind is DecodeFailureKind.INVALID_DICOM
    assert "DICOM" in error.value.failure.message
    assert error.value.failure.remediation
