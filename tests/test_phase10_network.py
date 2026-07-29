"""Phase 10 SCP foundation tests."""

from __future__ import annotations

import asyncio
import concurrent.futures
import socket
import threading
from pathlib import Path
from collections.abc import Iterator
import pytest

from lumora_probe.associations.network import (
    DICOMListener,
    DICOMListenerConfig,
)
from lumora_probe.core.clock import SystemClock
from lumora_probe.core.ids import SeededUUIDv7Generator


@pytest.fixture
def free_port() -> Iterator[int]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    yield port


def _ids(count: int = 2) -> SeededUUIDv7Generator:
    return SeededUUIDv7Generator(
        [f"018f3f4e-7b00-7000-8000-{index:012x}" for index in range(1, count + 1)]
    )


class _RecordingIngress:
    def __init__(self) -> None:
        self.events: list[object] = []
        self.thread_names: list[str] = []

    def publish_from_thread(
        self, event: object, *, capture_id: str | None = None
    ) -> concurrent.futures.Future[object]:
        del capture_id
        self.events.append(event)
        self.thread_names.append(threading.current_thread().name)
        result: concurrent.futures.Future[object] = concurrent.futures.Future()
        result.set_result(event)
        return result


@pytest.mark.dicom
@pytest.mark.asyncio
async def test_listener_binds_non_privileged_configured_interface(free_port: int) -> None:
    listener = DICOMListener(
        DICOMListenerConfig(bind_host="127.0.0.1", port=free_port),
        clock=SystemClock(),
        id_generator=_ids(),
    )

    await listener.start()
    try:
        assert listener.started
        health = await listener.health()
        assert health.ready is True
        assert health.detail == f"127.0.0.1:{free_port}"
    finally:
        await listener.stop()


@pytest.mark.parametrize("port", [0, 104, 65536])
def test_listener_rejects_invalid_or_privileged_port(port: int) -> None:
    with pytest.raises(ValueError, match="non-privileged"):
        DICOMListenerConfig(port=port)


def test_listener_config_validates_ae_titles() -> None:
    with pytest.raises(Exception):
        DICOMListenerConfig(ae_title="too-long-ae-title-123")


def test_listener_config_normalizes_allowlist() -> None:
    config = DICOMListenerConfig(allowed_calling_aets=frozenset({"SCU_AE"}))
    assert config.allowed_calling_aets == frozenset({"SCU_AE"})


@pytest.mark.dicom
@pytest.mark.asyncio
async def test_scu_establishes_negotiates_echoes_and_releases(free_port: int) -> None:
    listener = DICOMListener(DICOMListenerConfig(port=free_port))
    await listener.start()
    try:
        from lumora_probe.associations.network import DICOMSCUClient, DICOMSCUConfig

        result = await DICOMSCUClient(
            DICOMSCUConfig(
                host="127.0.0.1",
                port=free_port,
                calling_ae="TEST-SCU",
                called_ae="LUMORA",
            )
        ).echo()

        assert result.success is True
        assert result.status == 0x0000
        assert result.error is None
    finally:
        await listener.stop()


@pytest.mark.dicom
@pytest.mark.asyncio
async def test_association_callbacks_use_thread_safe_event_ingress(free_port: int) -> None:
    from lumora_probe.associations.network import DICOMSCUClient, DICOMSCUConfig

    ingress = _RecordingIngress()
    listener = DICOMListener(
        DICOMListenerConfig(port=free_port),
        event_ingress=ingress,
        clock=SystemClock(),
        id_generator=_ids(8),
    )
    await listener.start()
    try:
        result = await DICOMSCUClient(
            DICOMSCUConfig(host="127.0.0.1", port=free_port, calling_ae="INGRESS-SCU")
        ).echo()

        assert result.success is True
        assert [event.event_name for event in ingress.events] == [
            "AssociationStarted",
            "AssociationAccepted",
            "CEchoReceived",
            "AssociationReleased",
        ]
        assert ingress.thread_names
        assert all(name != threading.current_thread().name for name in ingress.thread_names)
    finally:
        await listener.stop()


@pytest.mark.dicom
@pytest.mark.asyncio
async def test_association_audit_sink_logs_calling_ae_and_source_ip(free_port: int) -> None:
    from lumora_probe.associations.network import (
        DICOMSCUClient,
        DICOMSCUConfig,
        LoggingAssociationAuditSink,
    )

    class Logger:
        def __init__(self) -> None:
            self.entries: list[tuple[str, dict[str, object]]] = []

        def info(self, event: str, **values: object) -> None:
            self.entries.append((event, values))

    logger = Logger()
    listener = DICOMListener(
        DICOMListenerConfig(port=free_port),
        audit_sink=LoggingAssociationAuditSink(logger),
        clock=SystemClock(),
        id_generator=_ids(8),
    )
    await listener.start()
    try:
        result = await DICOMSCUClient(
            DICOMSCUConfig(host="127.0.0.1", port=free_port, calling_ae="AUDIT-SCU")
        ).echo()
        assert result.success is True
        assert [event for event, _ in logger.entries] == [
            "association_requested",
            "association_accepted",
            "association_released",
        ]
        for _, fields in logger.entries:
            assert fields["calling_ae"] == "AUDIT-SCU"
            assert fields["source_ip"] == "127.0.0.1"
            assert fields["association_id"]
    finally:
        await listener.stop()


@pytest.mark.dicom
@pytest.mark.asyncio
async def test_optional_calling_ae_allowlist_is_off_by_default_and_enforced_when_set(
    free_port: int,
) -> None:
    from lumora_probe.associations.network import DICOMSCUClient, DICOMSCUConfig

    denied_records = []
    listener = DICOMListener(
        DICOMListenerConfig(port=free_port, allowed_calling_aets=frozenset({"ALLOWED-SCU"})),
        audit_sink=denied_records.append,
        clock=SystemClock(),
        id_generator=_ids(12),
    )
    await listener.start()
    try:
        denied = await DICOMSCUClient(
            DICOMSCUConfig(host="127.0.0.1", port=free_port, calling_ae="DENIED-SCU")
        ).echo()
        assert denied.success is False
        assert any(record.phase == "rejected" for record in denied_records)

        accepted = await DICOMSCUClient(
            DICOMSCUConfig(host="127.0.0.1", port=free_port, calling_ae="ALLOWED-SCU")
        ).echo()
        assert accepted.success is True
    finally:
        await listener.stop()


def test_pass_through_negotiator_mirrors_only_upstream_accepted_contexts() -> None:
    from lumora_probe.associations.relay import PassThroughNegotiator

    plans = PassThroughNegotiator().mirror(
        [
            {
                "context_id": 1,
                "abstract_syntax": "1.2.3",
                "transfer_syntaxes": ["1.2.840.10008.1.2"],
            },
            {
                "context_id": 3,
                "abstract_syntax": "9.8.7",
                "transfer_syntaxes": ["1.2.840.10008.1.2.1"],
            },
        ],
        requested_abstract_syntaxes=["1.2.3"],
    )
    assert plans[0].abstract_syntax == "1.2.3"
    assert plans[0].transfer_syntaxes == ("1.2.840.10008.1.2",)


def test_byte_faithful_relay_preserves_malformed_bytes_and_records_diagnostic(
    tmp_path: Path,
) -> None:
    from lumora_probe.associations.relay import ByteFaithfulRelay, PDUTraceWriter

    diagnostics: list[tuple[str, dict[str, object]]] = []
    payload = b"\x04\x00\x00\x00\x00\x04bad"
    with PDUTraceWriter(tmp_path / "pdus.jsonl") as writer:
        relay = ByteFaithfulRelay(
            trace_writer=writer,
            trace_clock=lambda: 42,
            diagnostic_sink=lambda name, fields: diagnostics.append((name, dict(fields))),
        )
        sent: list[bytes] = []
        forwarded = relay.forward(
            payload,
            association_id="assoc-1",
            direction="downstream-to-upstream",
            send=sent.append,
        )

    assert forwarded == payload
    assert sent == [payload]
    assert diagnostics == [
        (
            "malformed-pdu",
            {"association_id": "assoc-1", "direction": "downstream-to-upstream", "length": 9},
        )
    ]
    assert '"pdu_type":"P-DATA-TF"' in (tmp_path / "pdus.jsonl").read_text()


def test_relay_requires_explicit_mode_for_standalone_capture() -> None:
    from lumora_probe.associations.relay import RelayConfig, RelayMode

    config = RelayConfig(mode=RelayMode.PASS_THROUGH)
    assert config.negotiation_label == "pass-through-upstream-unavailable"
    with pytest.raises(RuntimeError, match="choose permissive-standalone"):
        config.require_upstream()

    standalone = RelayConfig(mode=RelayMode.PERMISSIVE_STANDALONE)
    assert standalone.negotiation_label == "permissive-standalone"


def test_phase10_event_contracts_are_registered_and_catalogued() -> None:
    from lumora_probe.shared.events import DEFAULT_EVENT_REGISTRY, EventCategory

    for name, category in (
        ("CFindCompleted", EventCategory.DIMSE),
        ("InstancePersisted", EventCategory.DATASET),
        ("UnrecognizedDimseObserved", EventCategory.DIMSE),
    ):
        definition = DEFAULT_EVENT_REGISTRY.definition(name, 1)
        assert definition is not None
        assert definition.category is category


@pytest.mark.dicom
@pytest.mark.asyncio
async def test_inline_relay_forwards_c_echo_to_upstream_and_labels_mode(free_port: int) -> None:
    from lumora_probe.associations.network import DICOMSCUClient, DICOMSCUConfig
    from lumora_probe.associations.relay import DICOMRelay, RelayConfig, RelayMode

    upstream_port = free_port + 1
    upstream = DICOMListener(
        DICOMListenerConfig(port=upstream_port, ae_title="UPSTREAM"),
    )
    ingress = _RecordingIngress()
    relay = DICOMRelay(
        DICOMListenerConfig(port=free_port, ae_title="RELAY"),
        RelayConfig(
            mode=RelayMode.PASS_THROUGH,
            upstream=DICOMSCUConfig(
                host="127.0.0.1",
                port=upstream_port,
                calling_ae="RELAY-SCU",
                called_ae="UPSTREAM",
            ),
        ),
        event_ingress=ingress,
        clock=SystemClock(),
        id_generator=_ids(12),
    )
    await upstream.start()
    await relay.start()
    try:
        result = await DICOMSCUClient(
            DICOMSCUConfig(host="127.0.0.1", port=free_port, calling_ae="DOWNSTREAM")
        ).echo()
        assert result.success is True
        echo = next(event for event in ingress.events if event.event_name == "CEchoReceived")
        assert echo.payload["relay_mode"] == "pass-through"
        assert echo.payload["upstream_forwarded"] is True
        assert echo.payload["upstream_success"] is True
    finally:
        await relay.stop()
        await upstream.stop()


@pytest.mark.dicom
@pytest.mark.asyncio
async def test_inline_relay_forwards_c_store_and_publishes_enrichment_events(
    free_port: int,
) -> None:
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage

    from lumora_probe.associations.network import DICOMSCUClient, DICOMSCUConfig
    from lumora_probe.associations.relay import DICOMRelay, RelayConfig, RelayMode

    upstream_port = free_port + 1
    received: list[str] = []

    def store_sink(event: object) -> int:
        received.append(str(event.dataset.SOPInstanceUID))
        return 0x0000

    upstream = DICOMListener(
        DICOMListenerConfig(port=upstream_port, ae_title="UPSTREAM"),
        c_store_sink=store_sink,
    )
    ingress = _RecordingIngress()
    relay = DICOMRelay(
        DICOMListenerConfig(port=free_port, ae_title="RELAY"),
        RelayConfig(
            mode=RelayMode.PASS_THROUGH,
            upstream=DICOMSCUConfig(
                host="127.0.0.1",
                port=upstream_port,
                calling_ae="RELAY-SCU",
                called_ae="UPSTREAM",
            ),
        ),
        event_ingress=ingress,
        clock=SystemClock(),
        id_generator=_ids(20),
    )
    dataset = Dataset()
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.SOPInstanceUID = "1.2.826.0.1.3680043.10.543.10"
    dataset.StudyInstanceUID = "1.2.826.0.1.3680043.10.543.11"
    dataset.SeriesInstanceUID = "1.2.826.0.1.3680043.10.543.12"
    dataset.PatientName = "SYNTHETIC^TEST"
    dataset.file_meta = FileMetaDataset()
    dataset.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    await upstream.start()
    await relay.start()
    try:
        result = await asyncio.to_thread(
            DICOMSCUClient(
                DICOMSCUConfig(
                    host="127.0.0.1",
                    port=free_port,
                    calling_ae="DOWNSTREAM",
                    called_ae="RELAY",
                )
            ).store_dataset,
            dataset,
            abstract_syntax=str(SecondaryCaptureImageStorage),
            transfer_syntax=str(ExplicitVRLittleEndian),
            file_meta=dataset.file_meta,
        )
        assert result.success is True
        assert len(received) == 1
        assert received[0] == dataset.SOPInstanceUID
        names = [event.event_name for event in ingress.events]
        assert "CStoreReceived" in names
        assert "DatasetParsed" in names
        assert "InstancePersisted" in names
    finally:
        await relay.stop()
        await upstream.stop()


@pytest.mark.dicom
@pytest.mark.asyncio
async def test_pdu_trace_is_written_beside_bus_and_not_published_as_events(
    free_port: int, tmp_path: Path
) -> None:
    from lumora_probe.associations.network import DICOMSCUClient, DICOMSCUConfig
    from lumora_probe.associations.relay import PDUTraceWriter

    ingress = _RecordingIngress()
    with PDUTraceWriter(tmp_path / "pdus.jsonl") as writer:
        listener = DICOMListener(
            DICOMListenerConfig(port=free_port),
            event_ingress=ingress,
            pdu_trace_sink=writer,
            clock=SystemClock(),
            id_generator=_ids(20),
        )
        await listener.start()
        try:
            result = await DICOMSCUClient(
                DICOMSCUConfig(host="127.0.0.1", port=free_port, calling_ae="TRACE-SCU")
            ).echo()
            assert result.success is True
        finally:
            await listener.stop()

    rows = (tmp_path / "pdus.jsonl").read_text(encoding="utf-8").splitlines()
    assert rows
    assert all('"association_id"' in row for row in rows)
    assert all(event.event_name != "PDUReceived" for event in ingress.events)


@pytest.mark.dicom
@pytest.mark.asyncio
async def test_inline_relay_forwards_c_find_responses_and_completion_summary(
    free_port: int,
) -> None:
    from pydicom.dataset import Dataset
    from pynetdicom import AE, evt
    from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelFind

    from lumora_probe.associations.network import DICOMSCUClient, DICOMSCUConfig
    from lumora_probe.associations.relay import DICOMRelay, RelayConfig, RelayMode

    upstream_port = free_port + 1
    model = str(PatientRootQueryRetrieveInformationModelFind)
    upstream_ae = AE(ae_title="UPSTREAM")
    upstream_ae.add_supported_context(model)

    def on_find(event: object):
        response = Dataset()
        response.PatientName = "SYNTHETIC^FOUND"
        yield 0xFF00, response
        yield 0x0000, None

    upstream_server = upstream_ae.start_server(
        ("127.0.0.1", upstream_port),
        block=False,
        evt_handlers=[(evt.EVT_C_FIND, on_find)],
    )
    ingress = _RecordingIngress()
    relay = DICOMRelay(
        DICOMListenerConfig(port=free_port, ae_title="RELAY"),
        RelayConfig(
            mode=RelayMode.PASS_THROUGH,
            upstream=DICOMSCUConfig(
                host="127.0.0.1",
                port=upstream_port,
                calling_ae="RELAY-SCU",
                called_ae="UPSTREAM",
            ),
        ),
        event_ingress=ingress,
        clock=SystemClock(),
        id_generator=_ids(20),
    )
    await relay.start()
    try:
        identifier = Dataset()
        identifier.QueryRetrieveLevel = "PATIENT"
        responses = await asyncio.to_thread(
            lambda: list(
                DICOMSCUClient(
                    DICOMSCUConfig(
                        host="127.0.0.1",
                        port=free_port,
                        calling_ae="DOWNSTREAM",
                        called_ae="RELAY",
                    )
                ).iter_find(identifier, query_model=model)
            )
        )
        assert len(responses) == 2
        assert responses[0][1].PatientName == "SYNTHETIC^FOUND"
        assert [event.event_name for event in ingress.events if "Find" in event.event_name] == [
            "CFindReceived",
            "CFindCompleted",
        ]
        completed = next(event for event in ingress.events if event.event_name == "CFindCompleted")
        assert completed.payload["query_response_count"] == 2
    finally:
        await relay.stop()
        upstream_server.shutdown()
        upstream_ae.shutdown()


def test_unrecognized_dimse_is_recorded_without_abort() -> None:
    from types import SimpleNamespace

    from lumora_probe.associations.relay import DICOMRelay, RelayConfig, RelayMode

    ingress = _RecordingIngress()
    relay = DICOMRelay(
        DICOMListenerConfig(port=11112),
        RelayConfig(mode=RelayMode.PERMISSIVE_STANDALONE),
        event_ingress=ingress,
        clock=SystemClock(),
        id_generator=_ids(4),
    )
    event = SimpleNamespace(
        assoc=object(),
        request=SimpleNamespace(
            CommandField=0x0130,
            AffectedSOPClassUID="1.2.3",
            DataSet=b"malformed",
        ),
    )

    status = relay._on_unrecognized_dimse(event)

    assert status == 0x0122
    observed = ingress.events[-1]
    assert observed.event_name == "UnrecognizedDimseObserved"
    assert observed.payload["aborted"] is False
    assert observed.payload["dataset_present"] is True
