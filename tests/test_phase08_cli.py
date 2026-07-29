"""Tests for the Phase 08 live/offline CLI boundary."""

from __future__ import annotations

import json
from pathlib import Path

from lumora_probe.cli import inspect_capture, main


def test_offline_capture_inspection_reads_manifest(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    manifest = {"capture_id": "capture-1", "state": "sealed", "objects": []}
    capture_dir = tmp_path / "capture-1"
    capture_dir.mkdir()
    (capture_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert inspect_capture(capture_dir) == manifest
    assert main(["capture", "inspect", str(capture_dir)]) == 0
    assert json.loads(capsys.readouterr().out) == manifest
