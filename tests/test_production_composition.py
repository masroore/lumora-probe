"""Process-boundary acceptance tests for the shipped production composition."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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


def _dataset(index: int = 901) -> Dataset:
    dataset = Dataset()
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.SOPInstanceUID = f"1.2.826.0.1.3680043.10.543.{index}.3"
    dataset.StudyInstanceUID = f"1.2.826.0.1.3680043.10.543.{index}.1"
    dataset.SeriesInstanceUID = f"1.2.826.0.1.3680043.10.543.{index}.2"
    dataset.PatientName = "SYNTHETIC^PRODUCTION"
    dataset.file_meta = FileMetaDataset()
    dataset.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    return dataset


def _start(
    data_dir: Path,
    http_port: int,
    dicom_port: int,
    *,
    non_loopback: bool = True,
    shutdown_grace_seconds: float | None = None,
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
    if shutdown_grace_seconds is not None:
        environment["LUMORA_SHUTDOWN_GRACE_SECONDS"] = str(shutdown_grace_seconds)
    host = "0.0.0.0" if non_loopback else "127.0.0.1"
    trust = ["--trust-network"] if non_loopback else []
    command = ["uv", "run", "lumora", "serve"]
    if os.name == "nt":
        # Avoid leaving the uv shim's child holding captured pipes after termination.
        command = [sys.executable, "-m", "lumora_probe.cli", "serve"]
    command.extend(["--host", host, "--port", str(http_port), *trust])
    return subprocess.Popen(
        command,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _stop(process: subprocess.Popen[str]) -> tuple[str, str]:
    if process.poll() is None:
        if os.name == "nt":
            process.terminate()
        else:
            process.send_signal(signal.SIGTERM)
    try:
        stdout, stderr = process.communicate(timeout=15)
    except subprocess.TimeoutExpired as error:
        process.kill()
        process.communicate(timeout=5)
        raise AssertionError("production process required kill fallback") from error
    acceptable = {0, -signal.SIGTERM, 128 + signal.SIGTERM}
    if os.name == "nt":
        acceptable.add(1)
    assert process.returncode in acceptable
    return stdout, stderr


def _start_forced_deadline_process(
    data_dir: Path, http_port: int, dicom_port: int
) -> subprocess.Popen[str]:
    """Start the real composition with only the test-owned drain barrier wrapped."""
    script = r"""
import asyncio
import uvicorn

from lumora_probe.bootstrap import build_production_runtime
from lumora_probe.core.config import load_startup_config


async def main() -> None:
    config, _sources = load_startup_config()
    runtime = build_production_runtime(config)
    original_start = runtime.lifecycle.start
    original_drain = runtime.capture_engine.drain
    drain_entered = asyncio.Event()

    async def start() -> None:
        await original_start()
        await runtime.capture_engine.start_session(source="forced-process-test")

    async def drain() -> None:
        drain_entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            # Lifecycle cancels the timed-out drain before invoking interrupt.  Restore the
            # production method so interrupt_session can flush and seal the package.
            runtime.capture_engine.drain = original_drain
            raise
        await original_drain()

    runtime.lifecycle.start = start
    runtime.capture_engine.drain = drain
    server = uvicorn.Server(
        uvicorn.Config(runtime.app, host=config.bind_host, port=config.port, log_level="error")
    )
    await server.serve()


asyncio.run(main())
"""
    environment = os.environ.copy()
    environment.update(
        {
            "LUMORA_DATA_DIR": str(data_dir),
            "LUMORA_BIND_HOST": "127.0.0.1",
            "LUMORA_PORT": str(http_port),
            "LUMORA_DICOM_BIND_HOST": "127.0.0.1",
            "LUMORA_DICOM_PORT": str(dicom_port),
            "LUMORA_ALLOWED_HOSTS": "127.0.0.1,localhost",
            "LUMORA_SHUTDOWN_GRACE_SECONDS": "0.2",
        }
    )
    return subprocess.Popen(
        ["uv", "run", "python", "-c", script],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


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


@pytest.mark.component
@pytest.mark.dicom
@pytest.mark.slow
@pytest.mark.skipif(os.name == "nt", reason="SIGTERM evidence is POSIX-specific")
def test_production_process_drains_sustained_dicom_traffic(tmp_path: Path) -> None:
    """SIGTERM closes admission, drains acknowledged C-STOREs, and survives restart."""
    http_port = _free_port()
    dicom_port = _free_port()
    process = _start(tmp_path, http_port, dicom_port, shutdown_grace_seconds=5)
    base_url = f"http://127.0.0.1:{http_port}"
    successes: list[str] = []
    successes_lock = threading.Lock()
    stop_senders = threading.Event()
    run_started = datetime.now(UTC)

    try:
        _wait_ready(base_url)

        def send_loop(worker_id: int) -> None:
            index = worker_id * 10_000
            while not stop_senders.is_set():
                dataset = _dataset(index)
                client = DICOMSCUClient(
                    DICOMSCUConfig(
                        host="127.0.0.1",
                        port=dicom_port,
                        calling_ae=f"TRAFFIC{worker_id}",
                        called_ae="LUMORA",
                    )
                )
                result = client.store_dataset(
                    dataset,
                    abstract_syntax=str(SecondaryCaptureImageStorage),
                    transfer_syntax=str(ExplicitVRLittleEndian),
                    file_meta=dataset.file_meta,
                )
                if result.success:
                    with successes_lock:
                        successes.append(str(dataset.SOPInstanceUID))
                index += 1

        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(send_loop, worker_id) for worker_id in (1, 2)]
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                with successes_lock:
                    if len(successes) >= 4:
                        break
                time.sleep(0.05)
            else:
                raise AssertionError("sustained traffic did not produce four acknowledged C-STOREs")

            stop_senders.set()
            process.send_signal(signal.SIGTERM)
            try:
                try:
                    _stdout, stderr = process.communicate(timeout=20)
                except subprocess.TimeoutExpired as error:
                    process.kill()
                    process.communicate(timeout=5)
                    raise AssertionError("SIGTERM shutdown required kill fallback") from error
                assert process.returncode in {0, -signal.SIGTERM, 128 + signal.SIGTERM}
                assert "Task exception was never retrieved" not in stderr
                assert "unhandled exception" not in stderr.lower()
            finally:
                stop_senders.set()
            for future in futures:
                future.result(timeout=10)
    finally:
        stop_senders.set()
        if process.poll() is None:
            _stop(process)

    restarted_http = _free_port()
    restarted_dicom = _free_port()
    restarted = _start(tmp_path, restarted_http, restarted_dicom, shutdown_grace_seconds=5)
    try:
        restarted_url = f"http://127.0.0.1:{restarted_http}"
        _wait_ready(restarted_url)
        now = datetime.now(UTC)
        with httpx.Client(base_url=restarted_url, timeout=5) as client:
            promoted = client.post(
                "/api/v1/captures/ring-buffer/promote",
                json={
                    "start": (run_started - timedelta(seconds=1)).isoformat(),
                    "end": (now + timedelta(seconds=1)).isoformat(),
                },
            )
            assert promoted.status_code == 200, promoted.text
            instances = client.get("/api/v1/instances").json()["items"]
            durable_uids = {item["sop_instance_uid"] for item in instances}
            with successes_lock:
                acknowledged = set(successes)
            assert acknowledged <= durable_uids

        for manifest_path in (tmp_path / "captures").glob("*/manifest.json"):
            state = json.loads(manifest_path.read_text())["state"]
            assert state not in {"created", "running", "stopping"}
    finally:
        _stop(restarted)


@pytest.mark.component
@pytest.mark.dicom
@pytest.mark.slow
@pytest.mark.skipif(os.name == "nt", reason="SIGTERM evidence is POSIX-specific")
def test_forced_shutdown_marks_active_capture_interrupted_and_recovers(tmp_path: Path) -> None:
    """A real child process must interrupt, seal, and recover a capture after its deadline."""
    http_port = _free_port()
    dicom_port = _free_port()
    process = _start_forced_deadline_process(tmp_path, http_port, dicom_port)
    base_url = f"http://127.0.0.1:{http_port}"
    stop_sender = threading.Event()
    successes: list[str] = []

    def send_one() -> None:
        index = 98_000
        while not stop_sender.is_set():
            dataset = _dataset(index)
            try:
                result = DICOMSCUClient(
                    DICOMSCUConfig(
                        host="127.0.0.1",
                        port=dicom_port,
                        calling_ae="FORCED-SCU",
                        called_ae="LUMORA",
                    )
                ).store_dataset(
                    dataset,
                    abstract_syntax=str(SecondaryCaptureImageStorage),
                    transfer_syntax=str(ExplicitVRLittleEndian),
                    file_meta=dataset.file_meta,
                )
            except (OSError, RuntimeError, ValueError):  # network closes are expected at shutdown
                return
            if result.success:
                successes.append(str(dataset.SOPInstanceUID))
            index += 1

    sender = threading.Thread(target=send_one)
    try:
        _wait_ready(base_url)
        sender.start()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and not successes:
            time.sleep(0.05)
        assert successes, "forced-shutdown child did not acknowledge synthetic C-STORE traffic"

        stop_sender.set()
        process.send_signal(signal.SIGTERM)
        try:
            _stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired as error:
            process.kill()
            process.communicate(timeout=5)
            raise AssertionError("forced shutdown child required kill fallback") from error
        assert process.returncode in {0, -signal.SIGTERM, 128 + signal.SIGTERM, 143}, stderr
        assert "Task exception was never retrieved" not in stderr
    finally:
        stop_sender.set()
        sender.join(timeout=10)
        if process.poll() is None:
            _stop(process)

    manifests = list((tmp_path / "captures").glob("*/manifest.json"))
    assert manifests
    states = [json.loads(path.read_text()) for path in manifests]
    interrupted = [item for item in states if item["state"] == "interrupted"]
    assert interrupted
    assert all(item["interruption_reason"] for item in interrupted)

    restarted_http = _free_port()
    restarted_dicom = _free_port()
    restarted = _start(tmp_path, restarted_http, restarted_dicom, shutdown_grace_seconds=5)
    try:
        _wait_ready(f"http://127.0.0.1:{restarted_http}")
        assert all(
            json.loads(path.read_text())["state"] not in {"created", "running", "stopping"}
            for path in manifests
        )
    finally:
        _stop(restarted)
