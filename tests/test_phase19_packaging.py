"""Phase 19 packaging, installation, and offline UI checks."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from lumora_probe.core.config import StartupConfig
from lumora_probe.core.errors import VersionMismatchError
from lumora_probe.core.paths import DataPaths
from lumora_probe.web.api import create_app
from tests.test_phase19_distribution import _built_artifacts  # noqa: F401


def test_no_node_no_network_install_can_run_lumora_cli(
    built_artifacts: tuple[Path, Path], tmp_path: Path
) -> None:
    wheel, _source = built_artifacts
    target = tmp_path / "site"
    target.mkdir()
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--target",
            str(target),
            str(wheel),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    capture = tmp_path / "capture"
    capture.mkdir()
    (capture / "manifest.json").write_text(json.dumps({"capture_id": "offline"}), encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = ""
    env["PYTHONPATH"] = str(target)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lumora_probe.cli import main; raise SystemExit(main())",
            "capture",
            "inspect",
            str(capture),
        ],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == {"capture_id": "offline"}


@pytest.mark.asyncio
async def test_workspace_page_load_has_no_external_asset_requests() -> None:
    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/")
        css = await client.get("/static/css/app.css")
        renderer = await client.get("/static/js/cornerstone-renderer.js")

    assert response.status_code == 200
    assert not re.search(r"(?:href|src)=[\"'](?:https?:)?//", response.text, re.IGNORECASE)
    assert "/static/css/app.css" in response.text
    assert "/static/vendor/" in response.text
    assert css.status_code == 200
    assert renderer.status_code == 200


def test_newer_data_directory_is_refused_without_mutation(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    marker = data_root / "version"
    marker.write_text("99\n", encoding="utf-8")

    with pytest.raises(VersionMismatchError):
        DataPaths.from_config(StartupConfig(data_dir=data_root)).initialise()

    assert marker.read_text(encoding="utf-8") == "99\n"
