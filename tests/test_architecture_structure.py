"""Tests for the Phase 02 repository structure and import contracts."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SLICE_NAMES = (
    "core",
    "shared",
    "associations",
    "captures",
    "replay",
    "studies",
    "analysis",
    "reports",
    "plugins",
    "settings",
    "web",
)
BOUNDARY_MODULES = ("domain", "service", "repository", "api", "contracts")


def test_all_architecture_slices_have_public_boundaries() -> None:
    package_root = ROOT / "src" / "lumora_probe"

    assert (package_root / "__init__.py").is_file()
    for slice_name in SLICE_NAMES:
        slice_root = package_root / slice_name
        assert (slice_root / "__init__.py").is_file()
        for module_name in BOUNDARY_MODULES:
            assert (slice_root / f"{module_name}.py").is_file()


@pytest.mark.unit
def test_boundary_modules_are_importable() -> None:
    for slice_name in SLICE_NAMES:
        for module_name in BOUNDARY_MODULES:
            module = import_module(f"lumora_probe.{slice_name}.{module_name}")
            assert module.__all__ == ()
