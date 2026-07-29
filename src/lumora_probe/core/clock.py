"""Injected wall-clock and monotonic time primitives."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Clock contract exposing independent wall and monotonic time sources."""

    def now(self) -> datetime:
        """Return the current UTC wall-clock time."""
        ...

    def monotonic_ns(self) -> int:
        """Return a monotonic nanosecond counter for duration arithmetic."""
        ...


class SystemClock:
    """Production clock backed by the Python standard library."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()
