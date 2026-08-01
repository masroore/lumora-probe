"""Adversarial DICOM ingress and lifecycle tests for release closure."""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from typing import Any

import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage

from lumora_probe.associations.network import (
    DICOM_RESOURCE_EXHAUSTED,
    DICOM_SUCCESS,
    DICOMListener,
    DICOMListenerConfig,
    DICOMSCUClient,
    DICOMSCUConfig,
)
from lumora_probe.core.bus import ThreadIngressSaturatedError
from lumora_probe.core.clock import SystemClock
from lumora_probe.core.ids import UUIDv7Generator
from lumora_probe.shared.events import EventEnvelope


class _OneSlotIngress:
    """Hold one C-STORE event and refuse concurrent admissions deterministically."""

    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []
        self.first_c_store = threading.Event()
        self.saturated = threading.Event()
        self._release = concurrent.futures.Future[EventEnvelope]()
        self._lock = threading.Lock()
        self._held = False
        self._released = False
        self._held_event: EventEnvelope | None = None

    def publish_from_thread(
        self, event: EventEnvelope, *, capture_id: str | None = None
    ) -> concurrent.futures.Future[EventEnvelope]:
        del capture_id
        with self._lock:
            self.events.append(event)
            if event.event_name == "CStoreReceived" and not self._held:
                self._held = True
                self._held_event = event
                self.first_c_store.set()
                return self._release
            if event.event_name == "CStoreReceived" and not self._released:
                self.saturated.set()
                raise ThreadIngressSaturatedError()
        completed: concurrent.futures.Future[EventEnvelope] = concurrent.futures.Future()
        completed.set_result(event)
        return completed

    def release(self) -> None:
        with self._lock:
            self._released = True
        assert self._held_event is not None
        self._release.set_result(self._held_event)


class _ObjectSink:
    def __init__(self) -> None:
        self.uids: list[str] = []
        self._lock = threading.Lock()

    def __call__(self, event: Any) -> int:
        uid = str(event.dataset.SOPInstanceUID)
        with self._lock:
            self.uids.append(uid)
        return DICOM_SUCCESS


def _dataset(index: int) -> Dataset:
    uid_root = "1.2.826.0.1.3680043.10.543.930"
    instance = f"{uid_root}.{index}.3"
    dataset = Dataset()
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.SOPInstanceUID = instance
    dataset.StudyInstanceUID = f"{uid_root}.{index}.1"
    dataset.SeriesInstanceUID = f"{uid_root}.{index}.2"
    dataset.PatientName = "SATURATION^SYNTHETIC"
    dataset.file_meta = FileMetaDataset()
    dataset.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    return dataset


@pytest.mark.component
@pytest.mark.dicom
@pytest.mark.slow
@pytest.mark.asyncio
async def test_simultaneous_c_store_saturation_has_explicit_recovery(unused_tcp_port: int) -> None:
    ingress = _OneSlotIngress()
    sink = _ObjectSink()
    listener = DICOMListener(
        DICOMListenerConfig(port=unused_tcp_port, event_timeout_seconds=1.0),
        event_ingress=ingress,
        c_store_sink=sink,
        clock=SystemClock(),
        id_generator=UUIDv7Generator(),
    )
    await listener.start()
    try:

        async def send(index: int) -> Any:
            client = DICOMSCUClient(
                DICOMSCUConfig(
                    host="127.0.0.1",
                    port=unused_tcp_port,
                    calling_ae=f"SAT-{index}",
                    called_ae="LUMORA",
                )
            )
            return await asyncio.to_thread(
                client.store_dataset,
                _dataset(index),
                abstract_syntax=str(SecondaryCaptureImageStorage),
                transfer_syntax=str(ExplicitVRLittleEndian),
            )

        first = asyncio.create_task(send(1))
        await asyncio.wait_for(asyncio.to_thread(ingress.first_c_store.wait, 5), 6)
        second = asyncio.create_task(send(2))
        await asyncio.wait_for(asyncio.to_thread(ingress.saturated.wait, 5), 6)
        ingress.release()
        results = await asyncio.wait_for(asyncio.gather(first, second), 10)

        statuses = sorted(result.status for result in results)
        assert statuses == [DICOM_SUCCESS, DICOM_RESOURCE_EXHAUSTED]
        assert listener.diagnostic_counters["ingress_saturation"] >= 1
        assert set(sink.uids) == {
            "1.2.826.0.1.3680043.10.543.930.1.3",
            "1.2.826.0.1.3680043.10.543.930.2.3",
        }
        assert ingress.events
        assert {event.event_name for event in ingress.events} >= {"CStoreReceived", "DatasetParsed"}

        recovery = await send(3)
        assert recovery.status == DICOM_SUCCESS
        assert sink.uids[-1] == "1.2.826.0.1.3680043.10.543.930.3.3"
    finally:
        await listener.stop()
