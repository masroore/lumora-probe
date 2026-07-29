"""Tests for sender_lite.sender transport layer."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from sender_lite.catalog import CatalogInstance, SeriesCatalog, StudyBatch
from sender_lite.config import Config
from sender_lite.log import SenderLogger
from sender_lite.sender import EchoResult, Sender

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STUDY_UID = "1.2.3.4.5.100"
SERIES_UID = "1.2.3.4.5.100.1"
SOP_CLASS = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
TS_EXPLICIT = "1.2.840.10008.1.2.1"
TS_IMPLICIT = "1.2.840.10008.1.2"


def _make_config(**overrides: object) -> Config:
    defaults = {
        "input": None,
        "host": "127.0.0.1",
        "port": 11112,
        "calling_ae": "SENDER_LITE",
        "called_ae": "PROBE_LITE",
        "study_delay": 0.0,
        "connect_timeout": 5.0,
        "dimse_timeout": 5.0,
        "max_pdu": 16382,
        "log_format": "text",
        "verbose": False,
        "echo": False,
        "config_path": None,
    }
    defaults.update(overrides)
    return Config(**defaults)


def _make_instance(
    path: Path,
    sop_instance_uid: str = "1.2.3.4.5.6.7.8",
    sop_class_uid: str = SOP_CLASS,
    transfer_syntax_uid: str = TS_EXPLICIT,
    size_bytes: int = 100,
) -> CatalogInstance:
    return CatalogInstance(
        path=path,
        size_bytes=size_bytes,
        study_uid=STUDY_UID,
        series_uid=SERIES_UID,
        sop_instance_uid=sop_instance_uid,
        sop_class_uid=sop_class_uid,
        transfer_syntax_uid=transfer_syntax_uid,
        instance_number=1,
    )


def _make_study(instances: list[CatalogInstance]) -> StudyBatch:
    series = SeriesCatalog(series_uid=SERIES_UID, instances=tuple(instances))
    return StudyBatch(study_uid=STUDY_UID, series=(series,))


def _make_logger() -> SenderLogger:
    import io

    return SenderLogger(log_format="text", stream=io.StringIO())


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# ---------------------------------------------------------------------------
# Fake/Mock objects for unit tests
# ---------------------------------------------------------------------------


class FakeContext:
    def __init__(self, abstract_syntax: str, transfer_syntax: str) -> None:
        self.abstract_syntax = abstract_syntax
        self.transfer_syntax = transfer_syntax


class FakeAssociation:
    def __init__(
        self,
        established: bool = True,
        rejected: bool = False,
        aborted: bool = False,
        accepted_contexts: list[FakeContext] | None = None,
        rejected_contexts: list[FakeContext] | None = None,
        c_store_status: int | None = 0x0000,
        c_store_raises: Exception | None = None,
    ) -> None:
        self.is_established = established
        self.is_rejected = rejected
        self.is_aborted = aborted
        self.is_released = False
        self.accepted_contexts = accepted_contexts or []
        self.rejected_contexts = rejected_contexts or []
        self._c_store_status = c_store_status
        self._c_store_raises = c_store_raises
        self._c_store_calls = 0

    def send_c_echo(self) -> SimpleNamespace:
        return SimpleNamespace(Status=0x0000)

    def send_c_store(self, dataset: object, msg_id: int = 1) -> SimpleNamespace:
        self._c_store_calls += 1
        if self._c_store_raises is not None:
            self.is_established = False
            raise self._c_store_raises
        return SimpleNamespace(Status=self._c_store_status)

    def release(self) -> None:
        self.is_released = True
        self.is_established = False

    def abort(self) -> None:
        self.is_aborted = True
        self.is_established = False


class FakeAE:
    def __init__(self, assoc: FakeAssociation) -> None:
        self._assoc = assoc
        self.ae_title = ""
        self.connection_timeout = 0.0
        self.acse_timeout = 0.0
        self.dimse_timeout = 0.0
        self.network_timeout = 0.0
        self._contexts: list[object] = []

    def add_requested_context(
        self, abstract_syntax: str, transfer_syntax: str | list[str] | None = None
    ) -> None:
        self._contexts.append((abstract_syntax, transfer_syntax))

    def associate(
        self, host: str, port: int, ae_title: str = "", max_pdu: int = 16382
    ) -> FakeAssociation:
        return self._assoc


# ---------------------------------------------------------------------------
# Echo tests
# ---------------------------------------------------------------------------


def test_echo_success() -> None:
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    fake_assoc = FakeAssociation(established=True)
    fake_ae = FakeAE(fake_assoc)

    with patch("sender_lite.sender.pynetdicom") as mock_pn:
        mock_pn.AE.return_value = fake_ae
        result = sender.echo()

    assert isinstance(result, EchoResult)
    assert result.success is True
    assert result.status == 0x0000
    assert result.error is None
    assert result.duration >= 0.0


def test_echo_failure_non_zero_status() -> None:
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    fake_assoc = FakeAssociation(established=True)
    fake_assoc.send_c_echo = lambda: SimpleNamespace(Status=0x0122)  # type: ignore
    fake_ae = FakeAE(fake_assoc)

    with patch("sender_lite.sender.pynetdicom") as mock_pn:
        mock_pn.AE.return_value = fake_ae
        result = sender.echo()

    assert result.success is False
    assert result.status == 0x0122
    assert result.error is not None


def test_echo_associaton_failed() -> None:
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    fake_assoc = FakeAssociation(established=False, rejected=True)
    fake_ae = FakeAE(fake_assoc)

    with patch("sender_lite.sender.pynetdicom") as mock_pn:
        mock_pn.AE.return_value = fake_ae
        result = sender.echo()

    assert result.success is False
    assert result.status is None
    assert "rejected" in result.error.lower()


def test_echo_exception() -> None:
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    fake_ae = FakeAE(FakeAssociation(established=True))
    fake_ae.associate = MagicMock(side_effect=RuntimeError("boom"))

    with patch("sender_lite.sender.pynetdicom") as mock_pn:
        mock_pn.AE.return_value = fake_ae
        result = sender.echo()

    assert result.success is False
    assert "boom" in result.error


# ---------------------------------------------------------------------------
# send_study unit tests
# ---------------------------------------------------------------------------


def test_study_context_limit_129(tmp_path: Path) -> None:
    """129 contexts -> preflight fail, no network call."""
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    # Build 129 unique (sop_class, transfer_syntax) pairs
    instances = []
    for i in range(129):
        sop_class = f"1.2.3.4.{i}"
        inst = _make_instance(
            tmp_path / f"inst_{i}.dcm",
            sop_instance_uid=f"1.2.3.4.5.{i}",
            sop_class_uid=sop_class,
            transfer_syntax_uid=TS_EXPLICIT,
        )
        instances.append(inst)

    study = _make_study(instances)
    cancel = threading.Event()

    result = sender.send_study(study, cancel)

    assert result.attempted == 129
    assert result.failed == 129
    assert result.succeeded == 0
    assert result.error == "presentation_context_limit"
    assert all(i.reason == "presentation_context_limit" for i in result.instances)


def test_study_context_limit_128_accepted(tmp_path: Path) -> None:
    """128 contexts -> preflight passes, attempts association."""
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    instances = []
    for i in range(128):
        sop_class = f"1.2.3.4.{i}"
        inst = _make_instance(
            tmp_path / f"inst_{i}.dcm",
            sop_instance_uid=f"1.2.3.4.5.{i}",
            sop_class_uid=sop_class,
            transfer_syntax_uid=TS_EXPLICIT,
        )
        instances.append(inst)

    study = _make_study(instances)
    cancel = threading.Event()

    fake_assoc = FakeAssociation(established=False, rejected=True)
    fake_ae = FakeAE(fake_assoc)

    with patch("sender_lite.sender.pynetdicom") as mock_pn:
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        result = sender.send_study(study, cancel)

    assert result.attempted == 128
    assert result.failed == 128
    assert result.error != "presentation_context_limit"


def test_study_association_rejected(tmp_path: Path) -> None:
    """Association rejected -> all instances failed."""
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    inst1 = _make_instance(tmp_path / "inst1.dcm", sop_instance_uid="1.2.3.4.5.1")
    inst2 = _make_instance(tmp_path / "inst2.dcm", sop_instance_uid="1.2.3.4.5.2")
    study = _make_study([inst1, inst2])
    cancel = threading.Event()

    fake_assoc = FakeAssociation(established=False, rejected=True)
    fake_ae = FakeAE(fake_assoc)

    with patch("sender_lite.sender.pynetdicom") as mock_pn:
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        result = sender.send_study(study, cancel)

    assert result.attempted == 2
    assert result.failed == 2
    assert result.succeeded == 0
    assert "rejected" in result.error.lower()


def test_study_association_aborted(tmp_path: Path) -> None:
    """Association aborted -> all instances failed."""
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    inst1 = _make_instance(tmp_path / "inst1.dcm", sop_instance_uid="1.2.3.4.5.1")
    study = _make_study([inst1])
    cancel = threading.Event()

    fake_assoc = FakeAssociation(established=False, aborted=True)
    fake_ae = FakeAE(fake_assoc)

    with patch("sender_lite.sender.pynetdicom") as mock_pn:
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        result = sender.send_study(study, cancel)

    assert result.failed == 1
    assert "aborted" in result.error.lower()


def test_study_c_store_success(tmp_path: Path) -> None:
    """C-STORE success (0x0000)."""
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    inst_path = tmp_path / "inst.dcm"
    inst_path.write_bytes(b"fake")
    inst = _make_instance(inst_path, sop_instance_uid="1.2.3.4.5.1")
    study = _make_study([inst])
    cancel = threading.Event()

    accepted = [FakeContext(SOP_CLASS, TS_EXPLICIT)]
    fake_assoc = FakeAssociation(
        established=True, accepted_contexts=accepted, c_store_status=0x0000
    )
    fake_ae = FakeAE(fake_assoc)

    with (
        patch("sender_lite.sender.pynetdicom") as mock_pn,
        patch("sender_lite.sender.dcmread") as mock_dcmread,
    ):
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        mock_dcmread.return_value = SimpleNamespace(
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
            SOPInstanceUID="1.2.3.4.5.1",
            SOPClassUID=SOP_CLASS,
            file_meta=SimpleNamespace(TransferSyntaxUID=TS_EXPLICIT),
        )
        result = sender.send_study(study, cancel)

    assert result.succeeded == 1
    assert result.failed == 0
    assert result.instances[0].status == "success"
    assert result.instances[0].status_code == 0x0000


def test_study_c_store_warning(tmp_path: Path) -> None:
    """C-STORE warning (0xB000) -> warned, not failed."""
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    inst_path = tmp_path / "inst.dcm"
    inst_path.write_bytes(b"fake")
    inst = _make_instance(inst_path, sop_instance_uid="1.2.3.4.5.1")
    study = _make_study([inst])
    cancel = threading.Event()

    accepted = [FakeContext(SOP_CLASS, TS_EXPLICIT)]
    fake_assoc = FakeAssociation(
        established=True, accepted_contexts=accepted, c_store_status=0xB000
    )
    fake_ae = FakeAE(fake_assoc)

    with (
        patch("sender_lite.sender.pynetdicom") as mock_pn,
        patch("sender_lite.sender.dcmread") as mock_dcmread,
    ):
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        mock_dcmread.return_value = SimpleNamespace(
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
            SOPInstanceUID="1.2.3.4.5.1",
            SOPClassUID=SOP_CLASS,
            file_meta=SimpleNamespace(TransferSyntaxUID=TS_EXPLICIT),
        )
        result = sender.send_study(study, cancel)

    assert result.warned == 1
    assert result.failed == 0
    assert result.instances[0].status == "warning"


def test_study_c_store_failure(tmp_path: Path) -> None:
    """C-STORE failure (0xC000) -> failed, continues."""
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    inst_path1 = tmp_path / "inst1.dcm"
    inst_path1.write_bytes(b"fake")
    inst_path2 = tmp_path / "inst2.dcm"
    inst_path2.write_bytes(b"fake")
    inst1 = _make_instance(inst_path1, sop_instance_uid="1.2.3.4.5.1")
    inst2 = _make_instance(inst_path2, sop_instance_uid="1.2.3.4.5.2")
    study = _make_study([inst1, inst2])
    cancel = threading.Event()

    accepted = [FakeContext(SOP_CLASS, TS_EXPLICIT)]
    fake_assoc = FakeAssociation(
        established=True, accepted_contexts=accepted, c_store_status=0xC000
    )
    fake_ae = FakeAE(fake_assoc)

    with (
        patch("sender_lite.sender.pynetdicom") as mock_pn,
        patch("sender_lite.sender.dcmread") as mock_dcmread,
    ):
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        mock_dcmread.return_value = SimpleNamespace(
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
            SOPInstanceUID="1.2.3.4.5.1",
            SOPClassUID=SOP_CLASS,
            file_meta=SimpleNamespace(TransferSyntaxUID=TS_EXPLICIT),
        )
        result = sender.send_study(study, cancel)

    assert result.failed == 2
    assert result.succeeded == 0
    assert all(i.status == "failure" for i in result.instances)


def test_study_exact_context_rejection(tmp_path: Path) -> None:
    """Exact context rejection -> affected instances failed, others sent."""
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    inst_path1 = tmp_path / "inst1.dcm"
    inst_path1.write_bytes(b"fake")
    inst_path2 = tmp_path / "inst2.dcm"
    inst_path2.write_bytes(b"fake")
    inst1 = _make_instance(
        inst_path1, sop_instance_uid="1.2.3.4.5.1", transfer_syntax_uid=TS_EXPLICIT
    )
    inst2 = _make_instance(
        inst_path2, sop_instance_uid="1.2.3.4.5.2", transfer_syntax_uid=TS_IMPLICIT
    )
    study = _make_study([inst1, inst2])
    cancel = threading.Event()

    # Only TS_EXPLICIT accepted
    accepted = [FakeContext(SOP_CLASS, TS_EXPLICIT)]
    rejected = [FakeContext(SOP_CLASS, TS_IMPLICIT)]
    fake_assoc = FakeAssociation(
        established=True,
        accepted_contexts=accepted,
        rejected_contexts=rejected,
        c_store_status=0x0000,
    )
    fake_ae = FakeAE(fake_assoc)

    def mock_dcmread_side_effect(path, force=False):
        if "inst1.dcm" in str(path):
            return SimpleNamespace(
                StudyInstanceUID=STUDY_UID,
                SeriesInstanceUID=SERIES_UID,
                SOPInstanceUID="1.2.3.4.5.1",
                SOPClassUID=SOP_CLASS,
                file_meta=SimpleNamespace(TransferSyntaxUID=TS_EXPLICIT),
            )
        else:
            return SimpleNamespace(
                StudyInstanceUID=STUDY_UID,
                SeriesInstanceUID=SERIES_UID,
                SOPInstanceUID="1.2.3.4.5.2",
                SOPClassUID=SOP_CLASS,
                file_meta=SimpleNamespace(TransferSyntaxUID=TS_IMPLICIT),
            )

    with (
        patch("sender_lite.sender.pynetdicom") as mock_pn,
        patch("sender_lite.sender.dcmread", side_effect=mock_dcmread_side_effect),
    ):
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        result = sender.send_study(study, cancel)

    assert result.succeeded == 1
    assert result.failed == 1
    assert result.instances[0].status == "success"
    assert result.instances[1].status == "failure"
    assert result.instances[1].reason == "context_rejected"


def test_study_mixed_contexts(tmp_path: Path) -> None:
    """Mixed accepted/rejected contexts -> partial study result."""
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    inst_path1 = tmp_path / "inst1.dcm"
    inst_path1.write_bytes(b"fake")
    inst_path2 = tmp_path / "inst2.dcm"
    inst_path2.write_bytes(b"fake")
    inst1 = _make_instance(inst_path1, sop_instance_uid="1.2.3.4.5.1", sop_class_uid=SOP_CLASS)
    inst2 = _make_instance(inst_path2, sop_instance_uid="1.2.3.4.5.2", sop_class_uid="1.2.3.4.999")
    study = _make_study([inst1, inst2])
    cancel = threading.Event()

    # Only first SOP class accepted
    accepted = [FakeContext(SOP_CLASS, TS_EXPLICIT)]
    fake_assoc = FakeAssociation(
        established=True, accepted_contexts=accepted, c_store_status=0x0000
    )
    fake_ae = FakeAE(fake_assoc)

    def mock_dcmread_side_effect(path, force=False):
        if "inst1.dcm" in str(path):
            return SimpleNamespace(
                StudyInstanceUID=STUDY_UID,
                SeriesInstanceUID=SERIES_UID,
                SOPInstanceUID="1.2.3.4.5.1",
                SOPClassUID=SOP_CLASS,
                file_meta=SimpleNamespace(TransferSyntaxUID=TS_EXPLICIT),
            )
        else:
            return SimpleNamespace(
                StudyInstanceUID=STUDY_UID,
                SeriesInstanceUID=SERIES_UID,
                SOPInstanceUID="1.2.3.4.5.2",
                SOPClassUID="1.2.3.4.999",
                file_meta=SimpleNamespace(TransferSyntaxUID=TS_EXPLICIT),
            )

    with (
        patch("sender_lite.sender.pynetdicom") as mock_pn,
        patch("sender_lite.sender.dcmread", side_effect=mock_dcmread_side_effect),
    ):
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        result = sender.send_study(study, cancel)

    assert result.succeeded == 1
    assert result.failed == 1
    assert result.instances[0].status == "success"
    assert result.instances[1].status == "failure"
    assert result.instances[1].reason == "context_rejected"


def test_study_mid_association_loss(tmp_path: Path) -> None:
    """Mid-study association loss -> fail unsent remainder."""
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    inst_path1 = tmp_path / "inst1.dcm"
    inst_path1.write_bytes(b"fake")
    inst_path2 = tmp_path / "inst2.dcm"
    inst_path2.write_bytes(b"fake")
    inst1 = _make_instance(inst_path1, sop_instance_uid="1.2.3.4.5.1")
    inst2 = _make_instance(inst_path2, sop_instance_uid="1.2.3.4.5.2")
    study = _make_study([inst1, inst2])
    cancel = threading.Event()

    accepted = [FakeContext(SOP_CLASS, TS_EXPLICIT)]
    # First send raises exception, association becomes unusable
    fake_assoc = FakeAssociation(established=True, accepted_contexts=accepted)
    fake_assoc._c_store_raises = RuntimeError("connection lost")
    fake_ae = FakeAE(fake_assoc)

    def mock_dcmread_side_effect(path, force=False):
        if "inst1.dcm" in str(path):
            return SimpleNamespace(
                StudyInstanceUID=STUDY_UID,
                SeriesInstanceUID=SERIES_UID,
                SOPInstanceUID="1.2.3.4.5.1",
                SOPClassUID=SOP_CLASS,
                file_meta=SimpleNamespace(TransferSyntaxUID=TS_EXPLICIT),
            )
        else:
            return SimpleNamespace(
                StudyInstanceUID=STUDY_UID,
                SeriesInstanceUID=SERIES_UID,
                SOPInstanceUID="1.2.3.4.5.2",
                SOPClassUID=SOP_CLASS,
                file_meta=SimpleNamespace(TransferSyntaxUID=TS_EXPLICIT),
            )

    with (
        patch("sender_lite.sender.pynetdicom") as mock_pn,
        patch("sender_lite.sender.dcmread", side_effect=mock_dcmread_side_effect),
    ):
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        result = sender.send_study(study, cancel)

    assert result.failed == 2
    assert result.instances[0].reason == "connection lost"
    assert result.instances[1].reason == "association_lost"


def test_study_revalidation_failure(tmp_path: Path) -> None:
    """Full-file revalidation failure -> that instance failed, continues."""
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    inst_path1 = tmp_path / "inst1.dcm"
    inst_path1.write_bytes(b"fake")
    inst_path2 = tmp_path / "inst2.dcm"
    inst_path2.write_bytes(b"fake")
    inst1 = _make_instance(inst_path1, sop_instance_uid="1.2.3.4.5.1")
    inst2 = _make_instance(inst_path2, sop_instance_uid="1.2.3.4.5.2")
    study = _make_study([inst1, inst2])
    cancel = threading.Event()

    accepted = [FakeContext(SOP_CLASS, TS_EXPLICIT)]
    fake_assoc = FakeAssociation(
        established=True, accepted_contexts=accepted, c_store_status=0x0000
    )
    fake_ae = FakeAE(fake_assoc)

    def mock_dcmread_side_effect(path, force=False):
        if "inst1.dcm" in str(path):
            # First instance: UID mismatch
            return SimpleNamespace(
                StudyInstanceUID="WRONG",
                SeriesInstanceUID=SERIES_UID,
                SOPInstanceUID="1.2.3.4.5.1",
                SOPClassUID=SOP_CLASS,
                file_meta=SimpleNamespace(TransferSyntaxUID=TS_EXPLICIT),
            )
        else:
            # Second instance: valid
            return SimpleNamespace(
                StudyInstanceUID=STUDY_UID,
                SeriesInstanceUID=SERIES_UID,
                SOPInstanceUID="1.2.3.4.5.2",
                SOPClassUID=SOP_CLASS,
                file_meta=SimpleNamespace(TransferSyntaxUID=TS_EXPLICIT),
            )

    with (
        patch("sender_lite.sender.pynetdicom") as mock_pn,
        patch("sender_lite.sender.dcmread", side_effect=mock_dcmread_side_effect),
    ):
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        result = sender.send_study(study, cancel)

    assert result.failed == 1
    assert result.succeeded == 1
    assert result.instances[0].status == "failure"
    assert result.instances[0].reason == "study_uid_changed"
    assert result.instances[1].status == "success"


def test_study_cancellation_before_first_send(tmp_path: Path) -> None:
    """Cancellation before first send -> all cancelled."""
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    inst_path = tmp_path / "inst.dcm"
    inst_path.write_bytes(b"fake")
    inst = _make_instance(inst_path, sop_instance_uid="1.2.3.4.5.1")
    study = _make_study([inst])
    cancel = threading.Event()
    cancel.set()  # Cancel immediately

    accepted = [FakeContext(SOP_CLASS, TS_EXPLICIT)]
    fake_assoc = FakeAssociation(established=True, accepted_contexts=accepted)
    fake_ae = FakeAE(fake_assoc)

    with patch("sender_lite.sender.pynetdicom") as mock_pn:
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        result = sender.send_study(study, cancel)

    assert result.cancelled == 1
    assert result.succeeded == 0
    assert result.instances[0].status == "cancelled"


def test_study_cancellation_between_sends(tmp_path: Path) -> None:
    """Cancellation between sends -> remaining cancelled."""
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    inst_path1 = tmp_path / "inst1.dcm"
    inst_path1.write_bytes(b"fake")
    inst_path2 = tmp_path / "inst2.dcm"
    inst_path2.write_bytes(b"fake")
    inst1 = _make_instance(inst_path1, sop_instance_uid="1.2.3.4.5.1")
    inst2 = _make_instance(inst_path2, sop_instance_uid="1.2.3.4.5.2")
    study = _make_study([inst1, inst2])
    cancel = threading.Event()

    accepted = [FakeContext(SOP_CLASS, TS_EXPLICIT)]
    fake_assoc = FakeAssociation(
        established=True, accepted_contexts=accepted, c_store_status=0x0000
    )
    fake_ae = FakeAE(fake_assoc)

    call_count = 0

    def mock_dcmread_side_effect(path, force=False):
        return SimpleNamespace(
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
            SOPInstanceUID="1.2.3.4.5.1",
            SOPClassUID=SOP_CLASS,
            file_meta=SimpleNamespace(TransferSyntaxUID=TS_EXPLICIT),
        )

    # Cancel after first send
    original_send_c_store = fake_assoc.send_c_store

    def send_c_store_with_cancel(dataset, msg_id=1):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            cancel.set()  # Cancel after first send
        return original_send_c_store(dataset, msg_id)

    fake_assoc.send_c_store = send_c_store_with_cancel  # type: ignore

    with (
        patch("sender_lite.sender.pynetdicom") as mock_pn,
        patch("sender_lite.sender.dcmread", side_effect=mock_dcmread_side_effect),
    ):
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        result = sender.send_study(study, cancel)

    assert result.succeeded == 1
    assert result.cancelled == 1
    assert result.instances[0].status == "success"
    assert result.instances[1].status == "cancelled"


def test_study_release_vs_abort(tmp_path: Path) -> None:
    """Release healthy association, abort unusable/cancelled."""
    config = _make_config()
    logger = _make_logger()
    sender = Sender(config, logger)

    inst_path = tmp_path / "inst.dcm"
    inst_path.write_bytes(b"fake")
    inst = _make_instance(inst_path, sop_instance_uid="1.2.3.4.5.1")
    study = _make_study([inst])
    cancel = threading.Event()

    accepted = [FakeContext(SOP_CLASS, TS_EXPLICIT)]
    fake_assoc = FakeAssociation(
        established=True, accepted_contexts=accepted, c_store_status=0x0000
    )
    fake_ae = FakeAE(fake_assoc)

    with (
        patch("sender_lite.sender.pynetdicom") as mock_pn,
        patch("sender_lite.sender.dcmread") as mock_dcmread,
    ):
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        mock_dcmread.return_value = SimpleNamespace(
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
            SOPInstanceUID="1.2.3.4.5.1",
            SOPClassUID=SOP_CLASS,
            file_meta=SimpleNamespace(TransferSyntaxUID=TS_EXPLICIT),
        )
        result = sender.send_study(study, cancel)

    assert result.succeeded == 1
    assert fake_assoc.is_released is True
    assert fake_assoc.is_aborted is False


# ---------------------------------------------------------------------------
# Integration tests with real ProbeReceiver
# ---------------------------------------------------------------------------


def _wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert predicate()


def _make_dicom_file(
    path: Path,
    study_uid: str = STUDY_UID,
    series_uid: str = SERIES_UID,
    sop_instance_uid: str = "1.2.3.4.5.6.7.8",
    sop_class_uid: str = SOP_CLASS,
    transfer_syntax: str = TS_EXPLICIT,
) -> Path:
    """Create a minimal DICOM file for testing."""
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import generate_uid

    if sop_instance_uid == "1.2.3.4.5.6.7.8":
        sop_instance_uid = generate_uid()

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.MediaStorageSOPClassUID = sop_class_uid
    file_meta.TransferSyntaxUID = transfer_syntax
    file_meta.MediaStorageApplicationTitle = "TEST"

    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\x00" * 128)
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.SOPInstanceUID = sop_instance_uid
    ds.SOPClassUID = sop_class_uid
    ds.PatientName = "TEST^PATIENT"
    ds.PatientID = "12345"
    ds.Modality = "CT"
    ds.InstanceNumber = 1
    ds.save_as(path, write_like_original=False)
    return path


def test_integration_echo_succeeds(tmp_path: Path) -> None:
    """Echo succeeds against ProbeReceiver."""
    pytest.importorskip("pydicom")
    pytest.importorskip("pynetdicom")
    from probe_lite.config import Config as ProbeConfig
    from probe_lite.receiver import ProbeReceiver

    port = _free_port()
    probe_config = ProbeConfig(port=port, output=tmp_path, log_format="text")
    receiver = ProbeReceiver(probe_config)
    receiver.start()
    _wait_until(lambda: receiver.server is not None)

    try:
        sender_config = _make_config(host="127.0.0.1", port=port, echo=True)
        logger = _make_logger()
        sender = Sender(sender_config, logger)
        result = sender.echo()

        assert result.success is True
        assert result.status == 0x0000
    finally:
        receiver.stop()


def test_integration_one_study_one_instance(tmp_path: Path) -> None:
    """One Study/one Instance -> one association, one stored file."""
    pytest.importorskip("pydicom")
    pytest.importorskip("pynetdicom")
    from probe_lite.config import Config as ProbeConfig
    from probe_lite.receiver import ProbeReceiver

    port = _free_port()
    probe_config = ProbeConfig(port=port, output=tmp_path, log_format="text")
    receiver = ProbeReceiver(probe_config)
    receiver.start()
    _wait_until(lambda: receiver.server is not None)

    try:
        # Create DICOM file
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        _make_dicom_file(input_dir / "test.dcm")

        sender_config = _make_config(host="127.0.0.1", port=port, input=input_dir)
        logger = _make_logger()
        sender = Sender(sender_config, logger)

        # Build catalog
        from sender_lite.catalog import build_catalog

        catalog = build_catalog(input_dir)
        assert catalog.study_count == 1
        study = catalog.studies[0]

        cancel = threading.Event()
        result = sender.send_study(study, cancel)

        assert result.succeeded == 1
        assert result.failed == 0
        assert receiver.total_instances == 1
        assert receiver.total_associations == 1
    finally:
        receiver.stop()


def test_integration_multiple_studies(tmp_path: Path) -> None:
    """Multiple Studies -> one association per Study."""
    pytest.importorskip("pydicom")
    pytest.importorskip("pynetdicom")
    from pydicom.uid import generate_uid

    from probe_lite.config import Config as ProbeConfig
    from probe_lite.receiver import ProbeReceiver

    port = _free_port()
    probe_config = ProbeConfig(port=port, output=tmp_path, log_format="text")
    receiver = ProbeReceiver(probe_config)
    receiver.start()
    _wait_until(lambda: receiver.server is not None)

    try:
        # Create 2 studies with 1 instance each
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        study1 = generate_uid()
        study2 = generate_uid()
        _make_dicom_file(input_dir / "test1.dcm", study_uid=study1, sop_instance_uid=generate_uid())
        _make_dicom_file(input_dir / "test2.dcm", study_uid=study2, sop_instance_uid=generate_uid())

        sender_config = _make_config(host="127.0.0.1", port=port, input=input_dir)
        logger = _make_logger()
        sender = Sender(sender_config, logger)

        # Build catalog
        from sender_lite.catalog import build_catalog

        catalog = build_catalog(input_dir)
        assert catalog.study_count == 2

        cancel = threading.Event()
        for study in catalog.studies:
            result = sender.send_study(study, cancel)
            assert result.succeeded == 1

        assert receiver.total_instances == 2
        assert receiver.total_associations == 2
    finally:
        receiver.stop()


def test_integration_transfer_syntax_preserved_implicit(tmp_path: Path) -> None:
    """Implicit VR Little Endian preserved."""
    pytest.importorskip("pydicom")
    pytest.importorskip("pynetdicom")
    from pydicom import dcmread

    from probe_lite.config import Config as ProbeConfig
    from probe_lite.receiver import ProbeReceiver

    port = _free_port()
    probe_config = ProbeConfig(port=port, output=tmp_path, log_format="text")
    receiver = ProbeReceiver(probe_config)
    receiver.start()
    _wait_until(lambda: receiver.server is not None)

    try:
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        _make_dicom_file(input_dir / "test.dcm", transfer_syntax=TS_IMPLICIT)

        sender_config = _make_config(host="127.0.0.1", port=port, input=input_dir)
        logger = _make_logger()
        sender = Sender(sender_config, logger)

        from sender_lite.catalog import build_catalog

        catalog = build_catalog(input_dir)
        study = catalog.studies[0]

        cancel = threading.Event()
        result = sender.send_study(study, cancel)

        assert result.succeeded == 1

        # Verify stored file has correct transfer syntax
        stored_files = [p for p in tmp_path.rglob("*.dcm") if input_dir not in p.parents]
        assert len(stored_files) == 1
        stored_ds = dcmread(stored_files[0], force=True)
        assert str(stored_ds.file_meta.TransferSyntaxUID) == TS_IMPLICIT
    finally:
        receiver.stop()


def test_integration_transfer_syntax_preserved_explicit(tmp_path: Path) -> None:
    """Explicit VR Little Endian preserved."""
    pytest.importorskip("pydicom")
    pytest.importorskip("pynetdicom")
    from pydicom import dcmread

    from probe_lite.config import Config as ProbeConfig
    from probe_lite.receiver import ProbeReceiver

    port = _free_port()
    probe_config = ProbeConfig(port=port, output=tmp_path, log_format="text")
    receiver = ProbeReceiver(probe_config)
    receiver.start()
    _wait_until(lambda: receiver.server is not None)

    try:
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        _make_dicom_file(input_dir / "test.dcm", transfer_syntax=TS_EXPLICIT)

        sender_config = _make_config(host="127.0.0.1", port=port, input=input_dir)
        logger = _make_logger()
        sender = Sender(sender_config, logger)

        from sender_lite.catalog import build_catalog

        catalog = build_catalog(input_dir)
        study = catalog.studies[0]

        cancel = threading.Event()
        result = sender.send_study(study, cancel)

        assert result.succeeded == 1

        # Verify stored file has correct transfer syntax
        stored_files = [p for p in tmp_path.rglob("*.dcm") if input_dir not in p.parents]
        assert len(stored_files) == 1
        stored_ds = dcmread(stored_files[0], force=True)
        assert str(stored_ds.file_meta.TransferSyntaxUID) == TS_EXPLICIT
    finally:
        receiver.stop()


# ---------------------------------------------------------------------------
# §14.2 event field conformance (plan section 14.2 "Required fields")
# ---------------------------------------------------------------------------


def _make_json_logger() -> SenderLogger:
    """Return a JSON logger whose stream can be parsed via ``logger._events()``."""
    import io
    import json

    stream = io.StringIO()
    logger = SenderLogger(log_format="json", stream=stream)

    def events() -> list[dict[str, object]]:
        return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]

    # Attach a callable to retrieve parsed events.
    logger._events = events  # type: ignore[attr-defined]
    return logger


def _make_json_logger_and_events() -> tuple[SenderLogger, object]:
    """Return a JSON logger and its parsed-event accessor."""
    logger = _make_json_logger()
    return logger, logger._events  # type: ignore[attr-defined]


def _send_success_study(
    config: Config, logger: SenderLogger, tmp_path: Path
) -> tuple[Sender, StudyBatch, threading.Event]:
    inst_path = tmp_path / "inst.dcm"
    inst_path.write_bytes(b"fake")
    inst = _make_instance(inst_path, sop_instance_uid="1.2.3.4.5.1")
    study = _make_study([inst])
    cancel = threading.Event()

    fake_assoc = FakeAssociation(
        established=True,
        accepted_contexts=[FakeContext(SOP_CLASS, TS_EXPLICIT)],
        c_store_status=0x0000,
    )
    fake_ae = FakeAE(fake_assoc)
    with (
        patch("sender_lite.sender.pynetdicom") as mock_pn,
        patch("sender_lite.sender.dcmread") as mock_dcmread,
    ):
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        mock_dcmread.return_value = SimpleNamespace(
            StudyInstanceUID=STUDY_UID,
            SeriesInstanceUID=SERIES_UID,
            SOPInstanceUID="1.2.3.4.5.1",
            SOPClassUID=SOP_CLASS,
            file_meta=SimpleNamespace(TransferSyntaxUID=TS_EXPLICIT),
        )
        sender = Sender(config, logger)
        sender.send_study(study, cancel, ordinal=1, total=1)
    return sender, study, cancel


def test_study_started_includes_required_fields(tmp_path: Path) -> None:
    logger = _make_json_logger()
    _send_success_study(_make_config(), logger, tmp_path)
    events = logger._events()  # type: ignore[attr-defined]
    started = next(e for e in events if e["event"] == "study_started")
    # §14.2: Study UID, Series, Instances, bytes, context count, ordinal/total
    assert started["study_uid"] == STUDY_UID
    assert started["series_count"] == 1
    assert started["instance_count"] == 1
    assert started["bytes"] == 100
    assert started["context_count"] == 1
    assert started["ordinal"] == 1
    assert started["total"] == 1


def test_instance_sent_includes_required_correlation_fields(tmp_path: Path) -> None:
    logger = _make_json_logger()
    _send_success_study(_make_config(), logger, tmp_path)
    events = logger._events()  # type: ignore[attr-defined]
    sent = next(e for e in events if e["event"] == "instance_sent")
    # §14.2: Study/Series/SOP UIDs, SOP Class UID, transfer syntax, path, bytes, status, duration
    assert sent["study_uid"] == STUDY_UID
    assert sent["series_uid"] == SERIES_UID
    assert sent["sop_instance_uid"] == "1.2.3.4.5.1"
    assert sent["sop_class_uid"] == SOP_CLASS
    assert sent["transfer_syntax_uid"] == TS_EXPLICIT
    assert "path" in sent
    assert sent["bytes"] == 100
    assert sent["status"] == "0x0000"
    assert "duration" in sent


def test_association_accepted_includes_peer_and_rejected_count(tmp_path: Path) -> None:
    logger = _make_json_logger()
    _send_success_study(_make_config(), logger, tmp_path)
    events = logger._events()  # type: ignore[attr-defined]
    accepted = next(e for e in events if e["event"] == "association_accepted")
    # §14.2: Study UID, peer, accepted/rejected context counts
    assert accepted["study_uid"] == STUDY_UID
    assert accepted["peer"] == "127.0.0.1:11112"
    assert accepted["accepted"] == 1
    assert accepted["rejected"] == 0


def test_verbose_emits_association_negotiation(tmp_path: Path) -> None:
    logger, _ = _make_json_logger_and_events()
    _send_success_study(_make_config(verbose=True), logger, tmp_path)
    events = logger._events()  # type: ignore[attr-defined]
    negotiation = [e for e in events if e["event"] == "association_negotiation"]
    assert len(negotiation) == 1
    neg = negotiation[0]
    assert neg["peer"] == "127.0.0.1:11112"
    assert neg["requested"] == 1
    assert neg["accepted"] == 1
    assert neg["rejected"] == 0


def test_non_verbose_omits_association_negotiation(tmp_path: Path) -> None:
    logger, _ = _make_json_logger_and_events()
    _send_success_study(_make_config(verbose=False), logger, tmp_path)
    events = logger._events()  # type: ignore[attr-defined]
    assert not any(e["event"] == "association_negotiation" for e in events)


def test_association_rejected_includes_peer_and_phase() -> None:
    import io
    import json

    stream = io.StringIO()
    logger = SenderLogger(log_format="json", stream=stream)
    config = _make_config()
    sender = Sender(config, logger)

    inst_path = Path("/tmp/__sender_lite_conf_rej__.dcm")
    study = _make_study([_make_instance(inst_path)])
    cancel = threading.Event()

    # Association that fails to establish.
    fake_assoc = FakeAssociation(established=False)
    fake_ae = FakeAE(fake_assoc)
    with patch("sender_lite.sender.pynetdicom") as mock_pn:
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        sender.send_study(study, cancel)

    events = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    rejected = next(e for e in events if e["event"] == "association_rejected")
    assert rejected["peer"] == "127.0.0.1:11112"
    assert rejected["phase"] == "establish"
    assert "reason" in rejected


def test_presentation_context_rejected_includes_affected_count() -> None:
    import io
    import json

    stream = io.StringIO()
    logger = SenderLogger(log_format="json", stream=stream)
    config = _make_config()
    sender = Sender(config, logger)

    inst_path = Path("/tmp/__sender_lite_conf_pcr__.dcm")
    study = _make_study([_make_instance(inst_path)])
    cancel = threading.Event()

    # Association accepts nothing, rejects our only context.
    fake_assoc = FakeAssociation(
        established=True,
        accepted_contexts=[],
        rejected_contexts=[FakeContext(SOP_CLASS, TS_EXPLICIT)],
    )
    fake_ae = FakeAE(fake_assoc)
    with (
        patch("sender_lite.sender.pynetdicom") as mock_pn,
        patch("sender_lite.sender.dcmread"),
    ):
        mock_pn.AE.return_value = fake_ae
        mock_pn.build_context = lambda sc, ts: FakeContext(sc, ts)
        sender.send_study(study, cancel)

    events = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    pcr = [e for e in events if e["event"] == "presentation_context_rejected"]
    assert len(pcr) == 1
    # §14.2: SOP Class UID, transfer syntax UID, affected Instance count
    assert pcr[0]["sop_class_uid"] == SOP_CLASS
    assert pcr[0]["transfer_syntax_uid"] == TS_EXPLICIT
    assert pcr[0]["affected_instance_count"] == 1
