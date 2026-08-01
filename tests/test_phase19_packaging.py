# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 19 packaging, installation, and offline UI checks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

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
            "from pathlib import Path; from lumora_probe.web.workspace_routes import STATIC_ROOT; assert (STATIC_ROOT / 'css/app.css').is_file(); from lumora_probe.cli import main; raise SystemExit(main())",
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
