# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 19 newer data-directory refusal verification."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumora_probe.core.config import StartupConfig
from lumora_probe.core.errors import VersionMismatchError
from lumora_probe.core.paths import DataPaths


def test_newer_data_directory_is_refused_without_mutation(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    marker = data_root / "version"
    marker.write_text("99\n", encoding="utf-8")

    with pytest.raises(VersionMismatchError):
        DataPaths.from_config(StartupConfig(data_dir=data_root)).initialise()

    assert marker.read_text(encoding="utf-8") == "99\n"
