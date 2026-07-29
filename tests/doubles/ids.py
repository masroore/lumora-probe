"""Deterministic UUIDv7 identity source for component tests."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from lumora_probe.core.ids import SeededUUIDv7Generator


class SeededIdGenerator(SeededUUIDv7Generator):
    """Readable test-double alias for the injected ID protocol."""

    def __init__(self, values: Iterable[UUID | str]) -> None:
        super().__init__(values)
