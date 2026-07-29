"""Empirically record the thread that executes pynetdicom EVT_C_STORE."""

from __future__ import annotations

import argparse
import socket
import threading
import time
from dataclasses import asdict, dataclass

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage
from pynetdicom import AE, evt


@dataclass(frozen=True, slots=True)
class ThreadObservation:
    main_thread_id: int
    main_thread_name: str
    store_thread_id: int
    store_thread_name: str
    store_thread_differs_from_main: bool
    handler_completed_before_send_return: bool


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _dataset() -> Dataset:
    file_meta = FileMetaDataset()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dataset = Dataset()
    dataset.file_meta = file_meta
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.SOPInstanceUID = "1.2.826.0.1.3680043.10.543.200"
    dataset.StudyInstanceUID = "1.2.826.0.1.3680043.10.543.201"
    dataset.SeriesInstanceUID = "1.2.826.0.1.3680043.10.543.202"
    dataset.PatientName = "SYNTHETIC^THREADING"
    dataset.PatientID = "SYNTHETIC-THREADING"
    dataset.Modality = "OT"
    return dataset


def observe() -> ThreadObservation:
    main_thread = threading.current_thread()
    store_thread_id: int | None = None
    store_thread_name: str | None = None
    handler_completed = threading.Event()

    def handle_store(event: object) -> int:
        nonlocal store_thread_id, store_thread_name
        store_thread = threading.current_thread()
        store_thread_id = store_thread.ident
        store_thread_name = store_thread.name
        handler_completed.set()
        return 0x0000

    port = _free_port()
    server_ae = AE(ae_title="LUMORA_SPIKE")
    server_ae.add_supported_context(SecondaryCaptureImageStorage)
    server = server_ae.start_server(
        ("127.0.0.1", port),
        block=False,
        evt_handlers=[(evt.EVT_C_STORE, handle_store)],
    )
    try:
        client_ae = AE(ae_title="SPIKE_CLIENT")
        client_ae.add_requested_context(SecondaryCaptureImageStorage, ExplicitVRLittleEndian)
        association = client_ae.associate("127.0.0.1", port, ae_title="LUMORA_SPIKE")
        if not association.is_established:
            raise RuntimeError("threading spike association was not established")
        association.send_c_store(_dataset())
        handler_completed_before_send_return = handler_completed.is_set()
        association.release()
        deadline = time.monotonic() + 2.0
        while not handler_completed.is_set() and time.monotonic() < deadline:
            time.sleep(0.01)
        if store_thread_id is None or store_thread_name is None:
            raise RuntimeError("EVT_C_STORE handler did not execute")
        return ThreadObservation(
            main_thread_id=main_thread.ident or -1,
            main_thread_name=main_thread.name,
            store_thread_id=store_thread_id,
            store_thread_name=store_thread_name,
            store_thread_differs_from_main=store_thread_id != main_thread.ident,
            handler_completed_before_send_return=handler_completed_before_send_return,
        )
    finally:
        server.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(asdict(observe()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
