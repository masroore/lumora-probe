"""Phase 18 startup-time measurement at the real process boundary."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_ready(base_url: str, *, timeout_s: float = 30.0) -> float:
    deadline = time.monotonic() + timeout_s
    started = time.monotonic()
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{base_url}/api/v1/health/ready", timeout=0.5)
            if response.status_code == 200:
                return time.monotonic() - started
        except httpx.HTTPError as error:
            last_error = error
        time.sleep(0.05)
    raise AssertionError(f"readiness timed out after {timeout_s}s: {last_error}")


@pytest.mark.component
@pytest.mark.slow
def test_lumora_serve_reaches_ready_five_times(tmp_path: Path) -> None:
    """Spawn five isolated serve processes; elapsed values are informational under Option B."""

    durations: list[float] = []
    composition_durations: list[float] = []
    for index in range(5):
        data_dir = tmp_path / f"data-{index}"
        port = _free_port()
        env = os.environ.copy()
        env["LUMORA_DATA_DIR"] = str(data_dir)
        env["LUMORA_BIND_HOST"] = "127.0.0.1"
        env["LUMORA_PORT"] = str(port)
        composition_started = time.monotonic()
        from lumora_probe.bootstrap import build_production_app
        from lumora_probe.core.config import StartupConfig

        build_production_app(StartupConfig(data_dir=data_dir, bind_host="127.0.0.1", port=port))
        composition_durations.append(time.monotonic() - composition_started)

        process = subprocess.Popen(
            ["uv", "run", "lumora", "serve", "--host", "127.0.0.1", "--port", str(port)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        try:
            durations.append(_wait_ready(f"http://127.0.0.1:{port}"))
        finally:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    assert len(durations) == 5
    assert all(duration > 0 for duration in durations)
    # Persist evidence for the performance report consumer via pytest capture.
    print(
        {
            "dimension": "startup",
            "serve_ready_seconds": durations,
            "build_production_app_seconds": composition_durations,
            "python": sys.version.split()[0],
            "platform": sys.platform,
        }
    )
