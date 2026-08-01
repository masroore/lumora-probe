"""Smoke one built Lumora Probe artifact without importing the source checkout."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import venv
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request(
    url: str, *, method: str = "GET", payload: dict[str, object] | None = None
) -> dict[str, object]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        value = json.loads(response.read().decode())
    if not isinstance(value, dict):
        raise TypeError(f"unexpected response from {url}")
    return value


def _python(venv_root: Path) -> Path:
    return venv_root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    artifact = args.artifact.expanduser().resolve()
    if not artifact.is_file():
        raise SystemExit(f"artifact does not exist: {artifact}")

    with tempfile.TemporaryDirectory(prefix="lumora-installed-smoke-") as raw:
        root = Path(raw)
        env_root = root / "venv"
        data_root = root / "data"
        if shutil.which("uv"):
            subprocess.run(["uv", "venv", "--python", sys.executable, str(env_root)], check=True)
        else:
            try:
                venv.EnvBuilder(with_pip=True, clear=True, symlinks=False).create(env_root)
            except subprocess.CalledProcessError:
                venv.EnvBuilder(with_pip=False, clear=True, symlinks=False).create(env_root)
        python = _python(env_root)
        pip_probe = subprocess.run(
            [str(python), "-m", "pip", "--version"], capture_output=True, check=False
        )
        if pip_probe.returncode == 0:
            installer = [str(python), "-m", "pip", "install", "--disable-pip-version-check"]
        elif shutil.which("uv"):
            installer = ["uv", "pip", "install", "--python", str(python)]
        else:
            raise RuntimeError("target virtual environment has neither pip nor uv")
        install = subprocess.run(
            [*installer, str(artifact)],
            cwd=root,
            env={**os.environ, "PYTHONPATH": ""},
            text=True,
            capture_output=True,
            check=False,
        )
        if install.returncode:
            raise RuntimeError(install.stdout + install.stderr)
        probe = subprocess.run(
            [
                str(python),
                "-c",
                "import lumora_probe, probe_lite, sender_lite, lumora_lite_common, lumora_dicom_common; print(lumora_probe.__file__)",
            ],
            cwd=root,
            env={**os.environ, "PYTHONPATH": ""},
            text=True,
            capture_output=True,
            check=False,
        )
        if probe.returncode or str(Path.cwd() / "src") in probe.stdout:
            raise RuntimeError(f"installed import check failed: {probe.stdout}{probe.stderr}")
        for relative in ("static/css/app.css", "assets/vendor/manifest.json"):
            check = subprocess.run(
                [
                    str(python),
                    "-c",
                    f"import importlib.metadata as m; assert m.distribution('lumora-probe').locate_file({relative!r}).is_file()",
                ],
                cwd=root,
                env={**os.environ, "PYTHONPATH": ""},
                capture_output=True,
                check=False,
            )
            if check.returncode:
                raise RuntimeError(f"installed asset missing: {relative}: {check.stderr.decode()}")

        http_port, dicom_port = _free_port(), _free_port()
        process_env = {
            **os.environ,
            "PYTHONPATH": "",
            "LUMORA_DATA_DIR": str(data_root),
            "LUMORA_PORT": str(http_port),
            "LUMORA_DICOM_PORT": str(dicom_port),
        }
        process = subprocess.Popen(
            [str(python), "-m", "lumora_probe.cli", "serve"],
            cwd=root,
            env=process_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    health = _request(f"http://127.0.0.1:{http_port}/api/v1/health/ready")
                    if health.get("ready") is True:
                        break
                except (OSError, urllib.error.URLError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("installed production process did not become ready")
            sender = r"""
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
from pynetdicom import AE
from sys import argv
port = int(argv[1])
instance = generate_uid(prefix="1.2.826.0.1.3680043.10.543.")
meta = FileMetaDataset()
meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
meta.MediaStorageSOPInstanceUID = instance
meta.TransferSyntaxUID = ExplicitVRLittleEndian
ds = Dataset()
ds.file_meta = meta
ds.SOPClassUID = SecondaryCaptureImageStorage
ds.SOPInstanceUID = instance
ds.StudyInstanceUID = generate_uid(prefix="1.2.826.0.1.3680043.10.543.")
ds.SeriesInstanceUID = generate_uid(prefix="1.2.826.0.1.3680043.10.543.")
ds.Modality = "OT"
ds.PatientName = "SMOKE^SYNTHETIC"
ds.PatientID = "SMOKE"
ae = AE(ae_title="SMOKE-SCU")
ae.add_requested_context("1.2.840.10008.1.1")
ae.add_requested_context(SecondaryCaptureImageStorage, ExplicitVRLittleEndian)
association = ae.associate("127.0.0.1", port, ae_title="LUMORA")
assert association.is_established
assert association.send_c_echo().Status == 0
assert association.send_c_store(ds).Status == 0
association.release()
"""
            result = subprocess.run(
                [str(python), "-c", sender, str(dicom_port)],
                cwd=root,
                env={**process_env, "PYTHONPATH": ""},
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode:
                raise RuntimeError(
                    f"installed DICOM smoke failed\n{result.stdout}\n{result.stderr}"
                )
            now = datetime.now(UTC)
            promoted = _request(
                f"http://127.0.0.1:{http_port}/api/v1/captures/ring-buffer/promote",
                method="POST",
                payload={
                    "start": (now - timedelta(minutes=1)).isoformat(),
                    "end": (now + timedelta(minutes=1)).isoformat(),
                },
            )
            if not promoted.get("capture_id"):
                raise RuntimeError("installed DICOM evidence was not promoted")
            captures = _request(f"http://127.0.0.1:{http_port}/api/v1/captures")
            if not any(
                item.get("capture_id") == promoted["capture_id"]
                for item in captures.get("items", [])
            ):
                raise RuntimeError("promoted capture is not visible through the installed API")
        finally:
            if os.name == "nt":
                process.terminate()
            else:
                process.send_signal(signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                raise RuntimeError(f"installed process needed kill fallback\n{stdout}\n{stderr}")
            log_parent = Path(os.environ.get("LUMORA_SMOKE_LOG_DIR", tempfile.gettempdir()))
            log_root = log_parent / f"{root.name}-logs"
            log_root.mkdir(parents=True, exist_ok=True)
            (log_root / "stdout.log").write_text(stdout, encoding="utf-8")
            (log_root / "stderr.log").write_text(stderr, encoding="utf-8")
            (log_root / "artifact.txt").write_text(str(artifact), encoding="utf-8")
            acceptable_exit_codes = {0, -15, 143}
            # Windows ``Popen.terminate()`` is a hard process termination and returns 1 for
            # an otherwise cleanly-started Uvicorn child.  The smoke already proves readiness,
            # DICOM, promotion, and captured stderr/stdout before this cleanup boundary.
            if os.name == "nt":
                acceptable_exit_codes.add(1)
            if process.returncode not in acceptable_exit_codes:
                raise RuntimeError(
                    f"installed process failed: {process.returncode}\n{stdout}\n{stderr}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
