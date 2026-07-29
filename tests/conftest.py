"""Shared test fixtures and harness configuration."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def repository_root() -> Path:
    """Return the repository root for fixture and script tests."""
    return Path(__file__).resolve().parents[1]
