from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import socket
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from probe_lite.config import Config
from probe_lite.receiver import (
    CANNOT_UNDERSTAND,
    DATASET_DOES_NOT_MATCH_SOP_CLASS,
    OUT_OF_RESOURCES,
    ProbeReceiver,
    SUCCESS,
)
from probe_lite.storage import StorageError


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _config(output: Path, **overrides: object) -> Config:
    values = {"port": _free_port(), "output": output}
    values.update(overrides)
    return Config(**values)


def test_c_store_write_failure_returns_a700(tmp_path: Path) -> None:
    receiver = ProbeReceiver(_config(tmp_path))
    receiver.storage = _FailingStorage()
    event = SimpleNamespace(
        request=SimpleNamespace(AffectedSOPInstanceUID="1.2.3"),
        dataset=object(),
        assoc=SimpleNamespace(),
    )

    assert receiver._on_c_store(event) == OUT_OF_RESOURCES


def test_unparseable_dataset_uses_raw_fallback(tmp_path: Path) -> None:
    receiver = ProbeReceiver(_config(tmp_path))

    class BrokenEvent:
        request = SimpleNamespace(AffectedSOPInstanceUID="1.2.3")
        assoc = SimpleNamespace()

        @property
        def dataset(self) -> object:
            raise ValueError("malformed dataset")

        def encoded_dataset(self) -> bytes:
            return b"malformed"

    assert receiver._on_c_store(BrokenEvent()) == DATASET_DOES_NOT_MATCH_SOP_CLASS
    assert (tmp_path / "1.2.3.dcm.raw").read_bytes() == b"malformed"


def test_malformed_request_returns_c000_when_raw_bytes_are_unavailable(tmp_path: Path) -> None:
    receiver = ProbeReceiver(_config(tmp_path))

    class MalformedEvent:
        request = SimpleNamespace(AffectedSOPInstanceUID="1.2.3")
        assoc = SimpleNamespace()

        @property
        def dataset(self) -> object:
            raise ValueError("malformed request")

        def encoded_dataset(self) -> bytes:
            raise ValueError("no decodable request payload")

    assert receiver._on_c_store(MalformedEvent()) == CANNOT_UNDERSTAND


@pytest.fixture
def dicom_stack() -> object:
    return pytest.importorskip("pydicom"), pytest.importorskip("pynetdicom")


def _make_dataset(pydicom: object, suffix: str) -> object:
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

    dataset = Dataset()
    dataset.PatientName = "TEST^PATIENT"
    dataset.StudyInstanceUID = generate_uid()
    dataset.SeriesInstanceUID = generate_uid()
    dataset.SOPInstanceUID = generate_uid()
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.Modality = "OT"
    dataset.InstanceNumber = suffix
    dataset.file_meta = FileMetaDataset()
    dataset.file_meta.MediaStorageSOPClassUID = dataset.SOPClassUID
    dataset.file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID
    dataset.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dataset.is_little_endian = True
    dataset.is_implicit_VR = False
    return dataset


def _set_transfer_syntax(dataset: object, transfer_syntax: str) -> None:
    dataset.file_meta.TransferSyntaxUID = transfer_syntax
    dataset.is_little_endian = transfer_syntax != "1.2.840.10008.1.2.2"
    dataset.is_implicit_VR = transfer_syntax == "1.2.840.10008.1.2"


def _start_receiver(tmp_path: Path, log_format: str = "json", **kwargs: object) -> ProbeReceiver:
    receiver = ProbeReceiver(_config(tmp_path, log_format=log_format, **kwargs))
    receiver.start()
    time.sleep(0.05)
    return receiver


def _send_store(
    pydicom: object, pynetdicom: object, receiver: ProbeReceiver, ae_title: str, dataset: object
) -> object:
    from pynetdicom import AE
    from pynetdicom.sop_class import SecondaryCaptureImageStorage, Verification
    from pydicom.uid import ExplicitVRLittleEndian

    sender = AE(ae_title=ae_title)
    sender.add_requested_context(Verification)
    sender.add_requested_context(SecondaryCaptureImageStorage, ExplicitVRLittleEndian)
    association = sender.associate(
        "127.0.0.1", receiver.config.port, ae_title=receiver.config.ae_title
    )
    assert association.is_established
    status = association.send_c_store(dataset)
    association.release()
    return status


def test_echo_and_store_round_trip(tmp_path: Path, dicom_stack: tuple[object, object]) -> None:
    pydicom, pynetdicom = dicom_stack
    receiver = _start_receiver(tmp_path)
    try:
        from pynetdicom import AE
        from pynetdicom.sop_class import SecondaryCaptureImageStorage, Verification
        from pydicom.uid import ExplicitVRLittleEndian

        sender = AE(ae_title="SENDER")
        sender.add_requested_context(Verification)
        sender.add_requested_context(SecondaryCaptureImageStorage, ExplicitVRLittleEndian)
        association = sender.associate(
            "127.0.0.1", receiver.config.port, ae_title=receiver.config.ae_title
        )
        assert association.is_established
        assert association.send_c_echo().Status == SUCCESS
        dataset = _make_dataset(pydicom, "1")
        assert association.send_c_store(dataset).Status == SUCCESS
        association.release()
        path = (
            tmp_path
            / dataset.StudyInstanceUID
            / dataset.SeriesInstanceUID
            / f"{dataset.SOPInstanceUID}.dcm"
        )
        assert path.exists()
        assert path.stat().st_size > 0
    finally:
        receiver.stop()


def test_multiple_instances_are_partitioned_by_study_and_series(
    tmp_path: Path, dicom_stack: tuple[object, object]
) -> None:
    pydicom, pynetdicom = dicom_stack
    receiver = _start_receiver(tmp_path)
    try:
        from pynetdicom import AE
        from pynetdicom.sop_class import SecondaryCaptureImageStorage
        from pydicom.uid import ExplicitVRLittleEndian

        sender = AE(ae_title="MULTI")
        sender.add_requested_context(SecondaryCaptureImageStorage, ExplicitVRLittleEndian)
        association = sender.associate(
            "127.0.0.1", receiver.config.port, ae_title=receiver.config.ae_title
        )
        assert association.is_established
        datasets = [_make_dataset(pydicom, str(index)) for index in range(3)]
        assert all(association.send_c_store(dataset).Status == SUCCESS for dataset in datasets)
        association.release()
        for dataset in datasets:
            assert (
                tmp_path
                / dataset.StudyInstanceUID
                / dataset.SeriesInstanceUID
                / f"{dataset.SOPInstanceUID}.dcm"
            ).exists()
    finally:
        receiver.stop()


def test_transfer_syntax_is_preserved(tmp_path: Path, dicom_stack: tuple[object, object]) -> None:
    pydicom, pynetdicom = dicom_stack
    receiver = _start_receiver(tmp_path)
    try:
        from pynetdicom import AE
        from pynetdicom.sop_class import SecondaryCaptureImageStorage
        from pydicom.uid import ExplicitVRBigEndian, ExplicitVRLittleEndian, ImplicitVRLittleEndian

        syntaxes = (ImplicitVRLittleEndian, ExplicitVRLittleEndian, ExplicitVRBigEndian)
        for index, transfer_syntax in enumerate(syntaxes):
            sender = AE(ae_title=f"TS{index}")
            sender.add_requested_context(SecondaryCaptureImageStorage, transfer_syntax)
            association = sender.associate(
                "127.0.0.1", receiver.config.port, ae_title=receiver.config.ae_title
            )
            assert association.is_established
            dataset = _make_dataset(pydicom, str(index))
            _set_transfer_syntax(dataset, transfer_syntax)
            assert association.send_c_store(dataset).Status == SUCCESS
            association.release()
            path = (
                tmp_path
                / dataset.StudyInstanceUID
                / dataset.SeriesInstanceUID
                / f"{dataset.SOPInstanceUID}.dcm"
            )
            saved = pydicom.dcmread(path, force=True)
            assert str(saved.file_meta.TransferSyntaxUID) == str(transfer_syntax)
    finally:
        receiver.stop()


def test_simultaneous_associations_are_served(
    tmp_path: Path, dicom_stack: tuple[object, object]
) -> None:
    pydicom, pynetdicom = dicom_stack
    receiver = _start_receiver(tmp_path)
    try:
        datasets = [_make_dataset(pydicom, str(index)) for index in range(4)]
        with ThreadPoolExecutor(max_workers=4) as executor:
            statuses = list(
                executor.map(
                    lambda item: _send_store(
                        pydicom, pynetdicom, receiver, f"SEND{item[0]}", item[1]
                    ),
                    enumerate(datasets),
                )
            )
        assert all(status.Status == SUCCESS for status in statuses)
        assert receiver.total_instances == len(datasets)
    finally:
        receiver.stop()


def test_stop_event_produces_clean_shutdown(
    tmp_path: Path, dicom_stack: tuple[object, object]
) -> None:
    pytest.importorskip("pydicom")
    pytest.importorskip("pynetdicom")
    receiver = ProbeReceiver(_config(tmp_path))
    stop_event = threading.Event()
    thread = threading.Thread(target=receiver.serve, args=(stop_event,))
    thread.start()
    time.sleep(0.05)
    stop_event.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert receiver.server is None


def test_rejected_calling_ae(tmp_path: Path, dicom_stack: tuple[object, object]) -> None:
    pytest.importorskip("pydicom")
    pytest.importorskip("pynetdicom")
    from pynetdicom import AE
    from pynetdicom.sop_class import Verification

    receiver = _start_receiver(tmp_path, accept_ae=frozenset({"ALLOWED"}))
    try:
        sender = AE(ae_title="REJECTED")
        sender.add_requested_context(Verification)
        association = sender.associate(
            "127.0.0.1", receiver.config.port, ae_title=receiver.config.ae_title
        )
        assert not association.is_established
    finally:
        receiver.stop()


class _FailingStorage:
    def write_dataset(self, dataset: object, file_meta: object = None) -> object:
        raise StorageError("disk full")
