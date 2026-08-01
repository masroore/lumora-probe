# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Deterministic wall and monotonic clocks for component tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lumora_probe.core.clock import Clock


class ControllableClock(Clock):
    def __init__(
        self,
        wall_time: datetime,
        *,
        monotonic_ns: int = 0,
    ) -> None:
        if wall_time.tzinfo is None or wall_time.utcoffset() is None:
            raise ValueError("wall_time must be timezone-aware")
        if monotonic_ns < 0:
            raise ValueError("monotonic_ns must be non-negative")
        self._wall_time = wall_time.astimezone(UTC)
        self._monotonic_ns = monotonic_ns

    def now(self) -> datetime:
        return self._wall_time

    def monotonic_ns(self) -> int:
        return self._monotonic_ns

    def set_wall_time(self, value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("wall_time must be timezone-aware")
        self._wall_time = value.astimezone(UTC)

    def advance_wall(self, delta: timedelta) -> None:
        self._wall_time += delta

    def set_monotonic_ns(self, value: int) -> None:
        if value < 0:
            raise ValueError("monotonic_ns must be non-negative")
        self._monotonic_ns = value

    def advance_monotonic_ns(self, delta: int) -> None:
        if delta < 0 or self._monotonic_ns + delta < 0:
            raise ValueError("monotonic delta must preserve a non-negative counter")
        self._monotonic_ns += delta
