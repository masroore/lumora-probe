"""Phase 10 SCP foundation tests."""

from __future__ import annotations

import concurrent.futures
import socket
import threading
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
            "AssociationReleased",
        ]
        assert ingress.thread_names
        assert all(name != threading.current_thread().name for name in ingress.thread_names)
    finally:
        await listener.stop()
