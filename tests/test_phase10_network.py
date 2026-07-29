"""Phase 10 SCP foundation tests."""

from __future__ import annotations

import socket
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


def _ids() -> SeededUUIDv7Generator:
    return SeededUUIDv7Generator(
        [
            "018f3f4e-7b00-7000-8000-000000000001",
            "018f3f4e-7b00-7000-8000-000000000002",
        ]
    )


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
