"""Process-boundary acceptance tests for the shipped production composition."""

from __future__ import annotations

import asyncio
import os
import signal
import socket
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage

from lumora_probe.associations.network import DICOMSCUClient, DICOMSCUConfig


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _assert_tcp_open(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=2):
        return


def _wait_ready(base_url: str, *, timeout: float = 30.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{base_url}/api/v1/health/ready", timeout=0.5)
            if response.status_code == 200:
                return response.json()
            last_error = RuntimeError(response.text)
        except httpx.HTTPError as error:
            last_error = error
        time.sleep(0.05)
    raise AssertionError(f"production app did not become ready: {last_error}")


def _dataset() -> Dataset:
    dataset = Dataset()
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.SOPInstanceUID = "1.2.826.0.1.3680043.10.543.901"
    dataset.StudyInstanceUID = "1.2.826.0.1.3680043.10.543.902"
    dataset.SeriesInstanceUID = "1.2.826.0.1.3680043.10.543.903"
    dataset.PatientName = "SYNTHETIC^PRODUCTION"
    dataset.file_meta = FileMetaDataset()
    dataset.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    return dataset


def _start(
    data_dir: Path, http_port: int, dicom_port: int, *, non_loopback: bool = True
) -> subprocess.Popen[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "LUMORA_DATA_DIR": str(data_dir),
            "LUMORA_BIND_HOST": "127.0.0.1",
            "LUMORA_PORT": str(http_port),
            "LUMORA_DICOM_BIND_HOST": "127.0.0.1",
            "LUMORA_DICOM_PORT": str(dicom_port),
            "LUMORA_ALLOWED_HOSTS": "127.0.0.1,localhost,probe.example" if non_loopback else "",
        }
    )
    host = "0.0.0.0" if non_loopback else "127.0.0.1"
    trust = ["--trust-network"] if non_loopback else []
    return subprocess.Popen(
        ["uv", "run", "lumora", "serve", "--host", host, "--port", str(http_port), *trust],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _stop(process: subprocess.Popen[str]) -> None:
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    assert process.returncode in {0, -signal.SIGTERM, 128 + signal.SIGTERM}


@pytest.mark.component
@pytest.mark.slow
def test_production_process_composes_dicom_capture_recovery_and_settings(tmp_path: Path) -> None:
    """The CLI process exposes the same live graph tested by component-level adapters."""
    http_port = _free_port()
    dicom_port = _free_port()
    process = _start(tmp_path, http_port, dicom_port)
    base_url = f"http://127.0.0.1:{http_port}"
    try:
        report = _wait_ready(base_url)
        names = {item["name"] for item in report["services"]}
        assert {
            "event-bus",
            "app-db",
            "index-db",
            "index-recovery",
            "capture-engine",
            "dicom-listener",
            "operation-jobs",
        } <= names

        _assert_tcp_open("127.0.0.1", dicom_port)
        with httpx.Client(base_url=base_url, timeout=5) as client:
            configured = client.get("/api/v1/health/live", headers={"host": "probe.example"})
            hostile = client.get("/api/v1/health/live", headers={"host": "evil.example"})
            assert configured.status_code == 200
            assert hostile.status_code == 400

        async def send_dicom() -> None:
            client = DICOMSCUClient(
                DICOMSCUConfig(
                    host="127.0.0.1",
                    port=dicom_port,
                    calling_ae="PRODUCTION-SCU",
                    called_ae="LUMORA",
                )
            )
            assert (await client.echo()).success
            dataset = _dataset()
            result = await asyncio.to_thread(
                client.store_dataset,
                dataset,
                abstract_syntax=str(SecondaryCaptureImageStorage),
                transfer_syntax=str(ExplicitVRLittleEndian),
                file_meta=dataset.file_meta,
            )
            assert result.success

        asyncio.run(send_dicom())
        now = datetime.now(UTC)
        with httpx.Client(base_url=base_url, timeout=5) as client:
            settings = client.get("/api/v1/settings")
            assert settings.status_code == 200
            assert {item["source"] for item in settings.json()["items"]} == {"default"}
            changed = client.patch("/api/v1/settings", json={"ring_buffer_seconds": 60})
            assert changed.status_code == 200
            promoted = client.post(
                "/api/v1/captures/ring-buffer/promote",
                json={
                    "start": (now - timedelta(minutes=1)).isoformat(),
                    "end": (now + timedelta(minutes=1)).isoformat(),
                },
            )
            assert promoted.status_code == 200, promoted.text
            capture_id = promoted.json()["capture_id"]
            captures = client.get("/api/v1/captures").json()
            assert any(item["capture_id"] == capture_id for item in captures["items"])
            instances = client.get("/api/v1/instances").json()
            instance = next(
                item
                for item in instances["items"]
                if item["sop_instance_uid"] == _dataset().SOPInstanceUID
            )
            metadata = client.get(f"/api/v1/instances/{instance['sop_instance_uid']}/metadata")
            assert metadata.status_code == 200
            report = client.get(f"/api/v1/captures/{capture_id}/report")
            assert report.status_code == 200
            started = client.post(
                f"/api/v1/captures/{capture_id}/report", params={"format": "json"}
            )
            assert started.status_code == 202
            operation_id = started.json()["operation_id"]
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                operation = client.get(f"/api/v1/operations/{operation_id}")
                assert operation.status_code == 200
                if operation.json()["state"] != "running":
                    break
                time.sleep(0.05)
            assert operation.json()["state"] == "completed"
    finally:
        _stop(process)

    restarted_http = _free_port()
    restarted_dicom = _free_port()
    restarted = _start(tmp_path, restarted_http, restarted_dicom)
    try:
        report = _wait_ready(f"http://127.0.0.1:{restarted_http}")
        assert report["ready"] is True
        with httpx.Client(base_url=f"http://127.0.0.1:{restarted_http}", timeout=5) as client:
            captures = client.get("/api/v1/captures").json()
            assert any(item["capture_id"] == capture_id for item in captures["items"])
            settings = client.get("/api/v1/settings").json()
            assert next(
                item for item in settings["items"] if item["name"] == "ring_buffer_seconds"
            ) == {"name": "ring_buffer_seconds", "value": 60, "source": "runtime"}
    finally:
        _stop(restarted)
