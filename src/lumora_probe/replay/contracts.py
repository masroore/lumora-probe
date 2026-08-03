# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Public contracts for offline event replay."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from lumora_probe.associations.contracts import DICOMStoreResult
from lumora_probe.shared.events import EventEnvelope
from lumora_probe.shared.value_objects import NetworkEndpoint


class ReplayTarget(BaseModel):
    """Explicit network destination for a protocol replay."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)

    @model_validator(mode="after")
    def validate_host(self) -> ReplayTarget:
        if any(character.isspace() for character in self.host):
            raise ValueError("target host must not contain whitespace")
        return self


class ReplayRequest(BaseModel):
    """Boundary request shared by replay preflight and creation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: ReplayMode
    capture_id: str = Field(min_length=1)
    fidelity: ReplayFidelity
    speed: float = Field(default=1.0, gt=0)
    dry_run: bool = True
    target: ReplayTarget | None = None
    target_confirmed: bool = False

    @model_validator(mode="after")
    def validate_invariants(self) -> ReplayRequest:
        if self.mode is ReplayMode.EVENT and self.fidelity is not ReplayFidelity.EVENTS:
            raise ValueError("event replay requires events fidelity")
        if self.mode is ReplayMode.PROTOCOL:
            if self.fidelity is ReplayFidelity.EVENTS:
                raise ValueError("protocol replay requires protocol or wire fidelity")
            if self.target is None:
                raise ValueError("protocol replay requires an explicit target")
            if not self.dry_run and not self.target_confirmed:
                raise ValueError(
                    "non-dry-run protocol replay requires explicit target confirmation"
                )
        return self


class ReplayOutcome(StrEnum):
    """Stable application-level preflight result."""

    ELIGIBLE = "eligible"
    REFUSED = "refused"


class ReplayPreflight(BaseModel):
    """Structured eligibility result that never starts background work."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: ReplayOutcome
    request: ReplayRequest
    planned_count: int = Field(default=0, ge=0)
    reasons: tuple[str, ...] = ()
    remediation: tuple[str, ...] = ()
    operation_id: str | None = None

    @computed_field
    @property
    def eligible(self) -> bool:
        """Return whether creation may proceed."""
        return self.outcome is ReplayOutcome.ELIGIBLE


class ReplayCaptureProvider(Protocol):
    """Capture evidence needed to preflight and execute replay."""

    async def describe(self, capture_id: str) -> Mapping[str, Any] | None: ...

    async def events(self, capture_id: str) -> list[Any] | tuple[Any, ...]: ...

    async def protocol_datasets(self, capture_id: str) -> list[Any] | tuple[Any, ...]: ...


class ReplayMode(StrEnum):
    """Replay execution mode."""

    EVENT = "event"
    PROTOCOL = "protocol"


class ReplayFidelity(StrEnum):
    """Evidence fidelity required by a replay mode."""

    EVENTS = "events"
    PROTOCOL = "protocol"
    WIRE = "wire"


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
        if not isinstance(self.raw_bytes, (bytes, bytearray, memoryview)):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("raw_bytes must be bytes-like")
        if not self.raw_bytes:
            raise ValueError("raw_bytes must not be empty")
        if not isinstance(self.transfer_syntax, str) or not self.transfer_syntax.strip():  # pyright: ignore[reportUnnecessaryIsInstance]
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

    replay_id: str | None
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


class ReplayCancellation(Protocol):
    """Cooperative cancellation probe supplied by the job registry."""

    @property
    def is_cancelled(self) -> bool:
        """Return whether replay should stop before the next send."""
        ...


class ReplayJobContext(Protocol):
    """Job context required by the application replay composition."""

    @property
    def operation_id(self) -> str:
        """Return the durable operation identity used as replay identity."""
        ...

    @property
    def cancellation(self) -> ReplayCancellation:
        """Return the cooperative cancellation probe."""
        ...

    async def report_progress(self, progress: Mapping[str, Any]) -> None:
        """Persist and publish one replay progress checkpoint."""
        ...


ReplayJobWorker = Callable[[ReplayJobContext], Awaitable[str | None]]


class ReplayJobRegistry(Protocol):
    """Application job registry used to compose replay into durable execution."""

    async def start(
        self,
        job_type: str,
        worker: ReplayJobWorker,
        *,
        parameters: Mapping[str, Any] = {},
    ) -> Any:
        """Start one background replay job."""
        ...

    async def startup_sweep(self, *, reason: str) -> int:
        """Mark all persisted/in-memory running jobs interrupted after restart."""
        ...


class ReplayAuditStore(Protocol):
    """Async persistence boundary for replay audit records."""

    async def append_replay_audit(self, record: Mapping[str, Any]) -> None:
        """Persist one replay audit record without blocking the event loop."""
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
    cancelled: bool = False

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
