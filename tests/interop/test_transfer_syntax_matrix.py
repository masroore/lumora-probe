# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Transfer-syntax matrix scenarios for Lumora's DICOM relay."""

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
_DCM4CHE_HOST = os.environ.get("LUMORA_INTEROP_HOST", "host.docker.internal")
_ORTHANC_UPSTREAM_PORT = 4242
_INPUT = "/fixtures/series-01/instance-01.dcm"
_SOP_CLASS = "1.2.840.10008.5.1.4.1.1.7"

_CASES = (
    pytest.param(
        "explicit-vr-little",
        (),
        "1.2.840.10008.1.2.1",
        "LittleEndianExplicit",
        id="explicit-vr-little",
    ),
    pytest.param(
        "rle-lossless",
        ("dcmcrle",),
        "1.2.840.10008.1.2.5",
        "RLELossless",
        id="rle-lossless",
    ),
    pytest.param(
        "jpeg-lossless-sv1",
        ("dcmcjpeg", "+e1"),
        "1.2.840.10008.1.2.4.70",
        "JPEGLossless:Non-hierarchical-1stOrderPrediction",
        id="jpeg-lossless-sv1",
    ),
    pytest.param(
        "jpeg-baseline",
        ("dcmcjpeg", "+eb"),
        "1.2.840.10008.1.2.4.50",
        "JPEGBaseline",
        id="jpeg-baseline",
    ),
    pytest.param(
        "jpeg-ls-lossless",
        ("dcmcjpls", "+el"),
        "1.2.840.10008.1.2.4.80",
        "JPEGLSLossless",
        id="jpeg-ls-lossless",
    ),
)


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


def _dcm4che(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(_COMPOSE_FILE),
            "exec",
            "-T",
            "dcm4che",
            *arguments,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _assert_succeeded(result: subprocess.CompletedProcess[str], tool: str) -> None:
    assert result.returncode == 0, (
        f"{tool} command failed with exit code {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def _relay(port: int) -> DICOMRelay:
    return DICOMRelay(
        DICOMListenerConfig(bind_host="0.0.0.0", port=port, ae_title="LUMORA"),
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


@pytest.mark.parametrize(
    ("name", "encoder", "transfer_syntax", "transfer_syntax_name"),
    _CASES,
)
@pytest.mark.asyncio
async def test_transfer_syntax_reaches_upstream_unchanged(
    free_port: int,
    name: str,
    encoder: tuple[str, ...],
    transfer_syntax: str,
    transfer_syntax_name: str,
) -> None:
    output = _INPUT
    if encoder:
        output = f"/matrix/lumora-{name}.dcm"
        encoded = await asyncio.to_thread(_dcmtk, *encoder, _INPUT, output)
        _assert_succeeded(encoded, "DCMTK encoder")

    inspected = await asyncio.to_thread(_dcmtk, "dcmdump", "+P", "0002,0010", output)
    _assert_succeeded(inspected, "DCMTK dcmdump")
    assert transfer_syntax_name in inspected.stdout

    relay = _relay(free_port)
    await relay.start()
    try:
        result = await asyncio.to_thread(
            _dcm4che,
            "storescu",
            "-b",
            "MATRIX-SCU",
            "-c",
            f"LUMORA@{_DCM4CHE_HOST}:{free_port}",
            "--store-tc",
            f"{_SOP_CLASS}:{transfer_syntax}",
            "--connect-timeout",
            "5000",
            "--response-timeout",
            "5000",
            output,
        )
    finally:
        await relay.stop()

    _assert_succeeded(result, "dcm4che storescu")
    assert "C-STORE-RSP" in result.stdout + result.stderr
    assert "status=0H" in result.stdout + result.stderr
