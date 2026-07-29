"""Public contracts for offline event replay."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from lumora_probe.associations.contracts import DICOMStoreResult
from lumora_probe.shared.events import EventEnvelope
from lumora_probe.shared.value_objects import NetworkEndpoint


class EventPublisher(Protocol):
    """Minimal event-bus ingress required by offline replay."""

    async def publish(
        self, event: EventEnvelope, *, capture_id: str | None = None
    ) -> EventEnvelope:
        """Publish an event and return the bus-sequenced envelope."""
        ...


@dataclass(frozen=True, slots=True)
class ProtocolReplayDataset:
    """Raw captured dataset and the timing metadata needed for protocol replay."""

    raw_bytes: bytes
    transfer_syntax: str
    monotonic_ns: int

    def __post_init__(self) -> None:
        if not isinstance(self.raw_bytes, (bytes, bytearray, memoryview)):
            raise TypeError("raw_bytes must be bytes-like")
        if not self.raw_bytes:
            raise ValueError("raw_bytes must not be empty")
        if not isinstance(self.transfer_syntax, str) or not self.transfer_syntax.strip():
            raise ValueError("transfer_syntax must be a non-empty string")
        if type(self.monotonic_ns) is not int or self.monotonic_ns < 0:
            raise ValueError("monotonic_ns must be a non-negative integer")
        object.__setattr__(self, "raw_bytes", bytes(self.raw_bytes))


@dataclass(frozen=True, slots=True)
class ProtocolReplayPolicy:
    """Explicit target, allowlist, and write mode for one protocol replay."""

    target: NetworkEndpoint | None = None
    allowed_targets: frozenset[NetworkEndpoint] = frozenset()
    dry_run: bool = True


@dataclass(frozen=True, slots=True)
class ProtocolReplayAuditRecord:
    """One immutable audit observation for a protocol replay run."""

    replay_id: str
    capture_id: str | None
    target: NetworkEndpoint | None
    dry_run: bool
    outcome: str
    planned_count: int
    confirmed_count: int
    failed_count: int
    occurred_at: datetime
    error: str | None = None


class ReplayAuditSink(Protocol):
    """Synchronous sink for protocol replay audit records."""

    def __call__(self, record: ProtocolReplayAuditRecord) -> None:
        """Persist or emit one audit record without blocking the event loop."""
        ...


@dataclass(frozen=True, slots=True)
class ProtocolReplayResult:
    """C-STORE results produced by one protocol replay."""

    results: tuple[DICOMStoreResult, ...]
    replay_id: str
    capture_id: str | None
    target: NetworkEndpoint
    dry_run: bool
    planned_count: int

    @property
    def count(self) -> int:
        """Return the number of datasets attempted during replay."""
        return len(self.results)

    @property
    def planned(self) -> int:
        """Return the number of datasets planned, including dry-run datasets."""
        return self.planned_count

    @property
    def success_count(self) -> int:
        """Return the number of successful C-STORE results."""
        return sum(result.success for result in self.results)

    @property
    def failure_count(self) -> int:
        """Return the number of unsuccessful C-STORE results."""
        return self.count - self.success_count


@dataclass(frozen=True, slots=True)
class EventReplayResult:
    """Published events produced by one offline event replay."""

    events: tuple[EventEnvelope, ...]
    replay_id: str
    correlation_id: str

    @property
    def count(self) -> int:
        """Return the number of events published during replay."""
        return len(self.events)


__all__: tuple[str, ...] = ()
