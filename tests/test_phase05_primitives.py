from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from lumora_probe.core.clock import SystemClock
from lumora_probe.core.ids import SeededUUIDv7Generator, UUIDv7Generator
from tests.doubles.clock import ControllableClock

_UUID_1 = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0b5"
_UUID_2 = "018f0c40-7d3d-7abd-8d2e-5b5a58fce0b5"


def test_controllable_clock_freezes_wall_and_monotonic_independently() -> None:
    clock = ControllableClock(datetime(2026, 7, 29, 12, tzinfo=UTC), monotonic_ns=100)
    clock.advance_wall(timedelta(seconds=5))
    assert clock.now() == datetime(2026, 7, 29, 12, 0, 5, tzinfo=UTC)
    assert clock.monotonic_ns() == 100

    clock.advance_monotonic_ns(900)
    assert clock.monotonic_ns() == 1000
    assert clock.now() == datetime(2026, 7, 29, 12, 0, 5, tzinfo=UTC)


def test_system_clock_returns_utc_and_monotonic_values() -> None:
    clock = SystemClock()
    assert clock.now().tzinfo is UTC
    assert clock.monotonic_ns() > 0


def test_seeded_uuidv7_generator_is_deterministic_and_exhaustion_is_explicit() -> None:
    generator = SeededUUIDv7Generator([_UUID_1, _UUID_2])
    assert generator.new_id() == _UUID_1
    assert generator.new_uuid() == UUID(_UUID_2)
    with pytest.raises(RuntimeError, match="exhausted"):
        generator.new_id()


def test_seeded_uuidv7_generator_rejects_non_v7_values() -> None:
    with pytest.raises(ValueError, match="not UUIDv7"):
        SeededUUIDv7Generator(["018f0c40-7d3d-6abc-8d2e-5b5a58fce0b5"])


def test_production_uuidv7_generator_emits_uuidv7() -> None:
    value = UUIDv7Generator().new_uuid()
    assert value.version == 7
    assert value.variant == UUID(_UUID_1).variant
