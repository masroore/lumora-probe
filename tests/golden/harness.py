# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Byte-comparison helpers for golden ``.lpcap`` fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GoldenMismatch:
    """Details for a byte mismatch between expected and actual output."""

    expected_size: int
    actual_size: int
    first_difference: int | None


class GoldenFixtureMismatch(AssertionError):
    """Raised when generated capture output differs from a golden fixture."""

    def __init__(self, fixture: Path, actual: Path, mismatch: GoldenMismatch) -> None:
        self.fixture = fixture
        self.actual = actual
        self.mismatch = mismatch
        super().__init__(
            f"golden fixture mismatch: expected={fixture} actual={actual} "
            f"expected_size={mismatch.expected_size} actual_size={mismatch.actual_size} "
            f"first_difference={mismatch.first_difference}"
        )


def _first_difference(expected: bytes, actual: bytes) -> int | None:
    for index, (expected_byte, actual_byte) in enumerate(zip(expected, actual, strict=False)):
        if expected_byte != actual_byte:
            return index
    if len(expected) != len(actual):
        return min(len(expected), len(actual))
    return None


def compare_bytes(fixture: Path, actual: Path) -> None:
    """Assert that two files are byte-identical."""
    expected_bytes = fixture.read_bytes()
    actual_bytes = actual.read_bytes()
    first_difference = _first_difference(expected_bytes, actual_bytes)
    if first_difference is not None:
        raise GoldenFixtureMismatch(
            fixture,
            actual,
            GoldenMismatch(
                expected_size=len(expected_bytes),
                actual_size=len(actual_bytes),
                first_difference=first_difference,
            ),
        )


def golden_path(root: Path, name: str) -> Path:
    """Resolve a named golden capture and reject path traversal."""
    if not name or Path(name).name != name or Path(name).suffix != ".lpcap":
        raise ValueError("golden fixture name must be a single .lpcap filename")
    resolved_root = root.resolve()
    resolved_path = (resolved_root / name).resolve()
    if resolved_path.parent != resolved_root:
        raise ValueError("golden fixture path escapes the fixture root")
    return resolved_path
