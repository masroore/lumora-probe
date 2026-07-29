"""Injected UUIDv7 identity generation."""

from __future__ import annotations

import secrets
import time
import uuid
from collections.abc import Iterable
from typing import Protocol


class IdGenerator(Protocol):
    """Identity source used by aggregates and event producers."""

    def new_uuid(self) -> uuid.UUID:
        """Return a fresh UUIDv7 identity."""
        ...

    def new_id(self) -> str:
        """Return a UUIDv7 identity in canonical string form."""
        ...


class UUIDv7Generator:
    """Generate UUIDv7 values without exposing the UUID implementation to callers."""

    def new_uuid(self) -> uuid.UUID:
        timestamp_ms = time.time_ns() // 1_000_000
        random_a = secrets.randbits(12)
        random_b = secrets.randbits(62)
        value = (
            ((timestamp_ms & ((1 << 48) - 1)) << 80)
            | (0x7 << 76)
            | (random_a << 64)
            | (0b10 << 62)
            | random_b
        )
        return uuid.UUID(int=value)

    def new_id(self) -> str:
        return str(self.new_uuid())

    generate = new_id


class SeededUUIDv7Generator:
    """Deterministic UUIDv7 source for component tests."""

    def __init__(self, values: Iterable[uuid.UUID | str]) -> None:
        self._values = tuple(_as_uuid7(value) for value in values)
        if not self._values:
            raise ValueError("seeded UUIDv7 generator requires at least one value")
        self._index = 0

    def new_uuid(self) -> uuid.UUID:
        if self._index >= len(self._values):
            raise RuntimeError("seeded UUIDv7 sequence exhausted")
        value = self._values[self._index]
        self._index += 1
        return value

    def new_id(self) -> str:
        return str(self.new_uuid())

    generate = new_id


def _as_uuid7(value: uuid.UUID | str) -> uuid.UUID:
    parsed = value if isinstance(value, uuid.UUID) else uuid.UUID(value)
    if parsed.version != 7:
        raise ValueError(f"seed value is not UUIDv7: {parsed}")
    return parsed
