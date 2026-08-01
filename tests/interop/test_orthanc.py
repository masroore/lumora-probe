# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Orthanc interoperability scenarios for Lumora's DICOM relay."""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from lumora_probe.associations.network import DICOMListenerConfig, DICOMSCUConfig
from lumora_probe.associations.relay import DICOMRelay, RelayConfig, RelayMode

pytestmark = [
    pytest.mark.dicom,
    pytest.mark.interop,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("LUMORA_INTEROP") != "1",
        reason="set LUMORA_INTEROP=1 and start tests/interop/docker-compose.yml",
    ),
]

_COMPOSE_FILE = Path(__file__).with_name("docker-compose.yml")
_DCMTK_HOST = os.environ.get("LUMORA_INTEROP_HOST", "host.docker.internal")
_ORTHANC_UPSTREAM_PORT = 4242


@pytest.fixture
def free_port() -> Iterator[int]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    yield port


def _dcmtk(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(_COMPOSE_FILE),
            "exec",
            "-T",
            "dcmtk",
            *arguments,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _assert_succeeded(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"DCMTK command failed with exit code {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def _relay(port: int, *, allowed_calling_aets: frozenset[str] = frozenset()) -> DICOMRelay:
    return DICOMRelay(
        DICOMListenerConfig(
            bind_host="0.0.0.0",
            port=port,
            ae_title="LUMORA",
            allowed_calling_aets=allowed_calling_aets,
        ),
        RelayConfig(
            mode=RelayMode.PASS_THROUGH,
            upstream=DICOMSCUConfig(
                host="127.0.0.1",
                port=_ORTHANC_UPSTREAM_PORT,
                calling_ae="LUMORA-RELAY",
                called_ae="ORTHANC",
            ),
        ),
    )


@pytest.mark.asyncio
async def test_dcmtk_echoscu_verifies_orthanc_through_lumora_relay(free_port: int) -> None:
    relay = _relay(free_port)
    await relay.start()
    try:
        result = await asyncio.to_thread(
            _dcmtk,
            "echoscu",
            "-v",
            "-aet",
            "DCMTK-SCU",
            "-aec",
            "LUMORA",
            "-to",
            "5",
            "-ta",
            "5",
            "-td",
            "5",
            _DCMTK_HOST,
            str(free_port),
        )
    finally:
        await relay.stop()

    _assert_succeeded(result)
    assert "Received Echo Response (Success)" in result.stderr


@pytest.mark.asyncio
async def test_dcmtk_storescu_sends_synthetic_instance_to_orthanc_through_relay(
    free_port: int,
) -> None:
    relay = _relay(free_port)
    await relay.start()
    try:
        result = await asyncio.to_thread(
            _dcmtk,
            "storescu",
            "-v",
            "-aet",
            "DCMTK-SCU",
            "-aec",
            "LUMORA",
            "-to",
            "5",
            "-ta",
            "5",
            "-td",
            "5",
            _DCMTK_HOST,
            str(free_port),
            "/fixtures/series-01/instance-02.dcm",
        )
    finally:
        await relay.stop()

    _assert_succeeded(result)
    assert "Received Store Response (Success)" in result.stderr
    assert "instance-02.dcm" in result.stderr


@pytest.mark.asyncio
async def test_dcmtk_calling_ae_rejection_is_explicit_and_orthanc_relay_recovers(
    free_port: int,
) -> None:
    relay = _relay(free_port, allowed_calling_aets=frozenset({"ALLOWED-SCU"}))
    await relay.start()
    try:
        denied = await asyncio.to_thread(
            _dcmtk,
            "echoscu",
            "-v",
            "-aet",
            "DENIED-SCU",
            "-aec",
            "LUMORA",
            "-to",
            "5",
            "-ta",
            "5",
            "-td",
            "5",
            _DCMTK_HOST,
            str(free_port),
        )
        allowed = await asyncio.to_thread(
            _dcmtk,
            "echoscu",
            "-v",
            "-aet",
            "ALLOWED-SCU",
            "-aec",
            "LUMORA",
            "-to",
            "5",
            "-ta",
            "5",
            "-td",
            "5",
            _DCMTK_HOST,
            str(free_port),
        )
    finally:
        await relay.stop()

    assert denied.returncode != 0
    assert "Association Rejected" in denied.stderr
    _assert_succeeded(allowed)
    assert "Received Echo Response (Success)" in allowed.stderr
