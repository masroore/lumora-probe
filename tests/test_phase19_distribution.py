# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 19 wheel and source distribution checks."""

from __future__ import annotations

import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="session", name="built_artifacts")
def _built_artifacts(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    output = tmp_path_factory.mktemp("package")
    subprocess.run(
        ["uv", "build", "--out-dir", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return next(output.glob("*.whl")), next(output.glob("*.tar.gz"))


def test_wheel_and_sdist_include_runtime_assets(built_artifacts: tuple[Path, Path]) -> None:
    wheel, source = built_artifacts

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata = archive.read("lumora_probe-0.1.0.dist-info/METADATA").decode()
    assert "Name: lumora-probe" in metadata
    assert "static/css/app.css" in names
    assert "static/js/cornerstone-renderer.js" in names
    assert "assets/vendor/manifest.json" in names
    for package in (
        "lumora_probe",
        "probe_lite",
        "sender_lite",
        "lumora_lite_common",
        "lumora_dicom_common",
    ):
        assert any(name.startswith(f"{package}/") for name in names), package

    with tarfile.open(source) as archive:
        names = set(archive.getnames())
    assert any(name.endswith("/static/css/app.css") for name in names)
    assert any(name.endswith("/assets/vendor/manifest.json") for name in names)
    assert any(name.endswith("/uv.lock") for name in names)
