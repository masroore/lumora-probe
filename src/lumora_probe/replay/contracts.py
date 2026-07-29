"""Public contracts for offline event replay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from lumora_probe.shared.events import EventEnvelope


class EventPublisher(Protocol):
    """Minimal event-bus ingress required by offline replay."""

    async def publish(
        self, event: EventEnvelope, *, capture_id: str | None = None
    ) -> EventEnvelope:
        """Publish an event and return the bus-sequenced envelope."""
        ...


@dataclass(frozen=True, slots=True)
class EventReplayResult:
    """Published events produced by one offline event replay."""

    events: tuple[EventEnvelope, ...]

    @property
    def count(self) -> int:
        """Return the number of events published during replay."""
        return len(self.events)


__all__: tuple[str, ...] = ()
