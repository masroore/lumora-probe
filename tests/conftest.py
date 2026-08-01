# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Shared test fixtures and harness configuration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def repository_root() -> Path:
    """Return the repository root for fixture and script tests."""
    return Path(__file__).resolve().parents[1]


def pytest_collection_modifyitems(config, items):
    """Skip browser e2e tests unless LUMORA_E2E=1 is set."""
    if os.environ.get("LUMORA_E2E") != "1":
        skip_e2e = pytest.mark.skip(reason="LUMORA_E2E=1 not set; browser e2e tests skipped")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)
