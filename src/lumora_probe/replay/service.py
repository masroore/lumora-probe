"""Offline event replay into the loop-owned event bus."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable, Iterable
from itertools import pairwise

from lumora_probe.associations.contracts import DICOMDatasetSender, DICOMStoreResult
from lumora_probe.shared.errors import ReplayDomainError
from lumora_probe.shared.events import EventClock, EventEnvelope, EventIdGenerator
from lumora_probe.shared.value_objects import NetworkEndpoint

from .contracts import (
    EventPublisher,
    EventReplayResult,
    ProtocolReplayAuditRecord,
    ProtocolReplayDataset,
    ProtocolReplayPolicy,
    ProtocolReplayResult,
    ReplayAuditSink,
    ReplayCancellation,
)

ReplaySleeper = Callable[[float], Awaitable[None]]


class InMemoryReplayExclusivity:
    """Refuse a second live protocol replay instead of queueing it."""

    def __init__(self) -> None:
        self._active = False

    def acquire(self) -> None:
        if self._active:
            raise ReplayDomainError(
                code="LUMORA-REPLAY-GUARD-003",
                message="A protocol replay is already running",
                remediation="Wait for the active protocol replay to finish before starting another.",
                context={"queued": False},
            )
        self._active = True

    def release(self) -> None:
        self._active = False


class ProtocolReplayService:
    """Replay captured DICOM datasets through an injected async sender."""

    def __init__(
        self,
        sender: DICOMDatasetSender,
        *,
        policy: ProtocolReplayPolicy,
        sleeper: ReplaySleeper | None = None,
        audit_sink: ReplayAuditSink | None = None,
        clock: EventClock | None = None,
        id_generator: EventIdGenerator | None = None,
        exclusivity: InMemoryReplayExclusivity | None = None,
    ) -> None:
        self.sender = sender
        self.policy = policy
        self.sleeper = sleeper if sleeper is not None else asyncio.sleep
        self.audit_sink = audit_sink
        self.clock = clock
        self.id_generator = id_generator
        self.exclusivity = exclusivity if exclusivity is not None else InMemoryReplayExclusivity()

    async def replay(
        self,
        datasets: Iterable[ProtocolReplayDataset],
        *,
        capture_fidelity: str,
        partial: bool = False,
        incomplete_aggregates: Iterable[str] = (),
        replay_id: str | None = None,
        capture_id: str | None = None,
        cancellation: ReplayCancellation | None = None,
        speed: float = 1.0,
    ) -> ProtocolReplayResult:
        """Send datasets in persisted order at original or scaled timing."""
        run_replay_id = replay_id or (
            self.id_generator.new_id() if self.id_generator is not None else None
        )
        if self.audit_sink is not None and run_replay_id is None:
            raise ValueError("protocol replay audit requires replay_id or id_generator")
        planned_count = 0
        acquired = False
        try:
            _require_protocol_fidelity(capture_fidelity)
            _require_complete_capture(partial, incomplete_aggregates)
            target = _validate_protocol_policy(self.policy)
            _validate_speed(speed)
            source_datasets = tuple(datasets)
            planned_count = len(source_datasets)
            _validate_protocol_monotonic_order(source_datasets)

            if self.policy.dry_run:
                result = ProtocolReplayResult(
                    results=(),
                    replay_id=run_replay_id,
                    capture_id=capture_id,
                    target=target,
                    dry_run=True,
                    planned_count=planned_count,
                    cancelled=False,
                )
                self._audit(result, outcome="dry-run")
                return result

            self.exclusivity.acquire()
            acquired = True
            results: list[DICOMStoreResult] = []
            cancelled = False
            for previous, dataset in _with_previous_dataset(source_datasets):
                if cancellation is not None and cancellation.is_cancelled:
                    cancelled = True
                    break
                if previous is not None:
                    delay_seconds = (dataset.monotonic_ns - previous.monotonic_ns) / 1_000_000_000
                    delay_seconds /= speed
                    if delay_seconds > 0:
                        await self.sleeper(delay_seconds)
                results.append(
                    await self.sender.send_dataset(
                        dataset.raw_bytes, transfer_syntax=dataset.transfer_syntax
                    )
                )
            result = ProtocolReplayResult(
                results=tuple(results),
                replay_id=run_replay_id,
                capture_id=capture_id,
                target=target,
                dry_run=False,
                planned_count=planned_count,
                cancelled=cancelled,
            )
            self._audit(result, outcome="cancelled" if cancelled else "completed")
            return result
        except Exception as exc:
            self._audit_refusal(
                replay_id=run_replay_id,
                capture_id=capture_id,
                planned_count=planned_count,
                error=str(exc),
            )
            raise
        finally:
            if acquired:
                self.exclusivity.release()

    def _audit(self, result: ProtocolReplayResult, *, outcome: str) -> None:
        if self.audit_sink is None:
            return
        if self.clock is None or result.replay_id is None:
            raise ValueError("protocol replay audit requires an injected clock and replay ID")
        self.audit_sink(
            ProtocolReplayAuditRecord(
                replay_id=result.replay_id,
                capture_id=result.capture_id,
                target=result.target,
                dry_run=result.dry_run,
                outcome=outcome,
                planned_count=result.planned_count,
                confirmed_count=result.success_count,
                failed_count=result.failure_count,
                occurred_at=self.clock.now(),
            )
        )

    def _audit_refusal(
        self,
        *,
        replay_id: str,
        capture_id: str | None,
        planned_count: int,
        error: str,
    ) -> None:
        if self.audit_sink is None:
            return
        if self.clock is None or not replay_id:
            raise ValueError("protocol replay audit requires an injected clock and replay ID")
        self.audit_sink(
            ProtocolReplayAuditRecord(
                replay_id=replay_id,
                capture_id=capture_id,
                target=self.policy.target,
                dry_run=self.policy.dry_run,
                outcome="refused",
                planned_count=planned_count,
                confirmed_count=0,
                failed_count=0,
                occurred_at=self.clock.now(),
                error=error,
            )
        )


class EventReplayService:
    """Re-emit persisted envelopes without network access or payload mutation.

    ``speed=1.0`` preserves the captured monotonic timing. Values greater than one
    accelerate replay; values between zero and one slow it down. Timing is derived
    only from ``monotonic_ns``. The caller supplies the event stream in persisted
    sequence order and may provide a capture key to keep the replay on one bus
    sequence.
    """

    def __init__(
        self,
        publisher: EventPublisher,
        *,
        sleeper: ReplaySleeper | None = None,
        id_generator: EventIdGenerator | None = None,
    ) -> None:
        self.publisher = publisher
        self.sleeper = sleeper if sleeper is not None else asyncio.sleep
        self.id_generator = id_generator

    async def replay(
        self,
        events: Iterable[EventEnvelope],
        *,
        capture_id: str | None = None,
        replay_id: str | None = None,
        speed: float = 1.0,
    ) -> EventReplayResult:
        """Replay envelopes into the bus at original or scaled timing."""
        _validate_speed(speed)
        source_events = tuple(events)
        _validate_monotonic_order(source_events)
        if self.id_generator is None:
            raise ValueError("event replay requires an injected id_generator")
        run_replay_id = replay_id or self.id_generator.new_id()
        replay_correlation_id = self.id_generator.new_id()

        published: list[EventEnvelope] = []
        for previous, event in _with_previous(source_events):
            if previous is not None:
                delay_seconds = (event.monotonic_ns - previous.monotonic_ns) / 1_000_000_000
                delay_seconds /= speed
                if delay_seconds > 0:
                    await self.sleeper(delay_seconds)
            replay_event = event.model_copy(
                update={
                    "event_id": self.id_generator.new_id(),
                    "correlation_id": replay_correlation_id,
                    "replay_id": run_replay_id,
                    "replay_of_event_id": event.event_id,
                    "sequence": None,
                }
            )
            published.append(await self.publisher.publish(replay_event, capture_id=capture_id))
        return EventReplayResult(tuple(published), run_replay_id, replay_correlation_id)


def _validate_speed(speed: float) -> None:
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError("replay speed must be a finite value greater than zero")


def _require_protocol_fidelity(capture_fidelity: str) -> None:
    if capture_fidelity not in {"protocol", "wire"}:
        raise ReplayDomainError(
            code="LUMORA-REPLAY-FID-001",
            message=(
                f"Protocol replay is unavailable for capture fidelity {capture_fidelity!r}; "
                "the protocol stream (pdus.jsonl) is missing"
            ),
            remediation="Use a capture with fidelity 'protocol' or 'wire'.",
            context={
                "capture_fidelity": capture_fidelity,
                "required_stream": "pdus.jsonl",
            },
        )


def _require_complete_capture(partial: bool, incomplete_aggregates: Iterable[str]) -> None:
    if not isinstance(partial, bool):
        raise TypeError("partial must be a boolean")
    incomplete = tuple(str(value) for value in incomplete_aggregates)
    if partial:
        detail = ", ".join(incomplete) if incomplete else "unspecified aggregate"
        raise ReplayDomainError(
            code="LUMORA-REPLAY-FID-002",
            message=f"Protocol replay is unavailable for a partial capture ({detail})",
            remediation="Promote a window containing the complete association negotiation.",
            context={"partial": True, "incomplete_aggregates": incomplete},
        )


def _validate_protocol_policy(policy: ProtocolReplayPolicy) -> NetworkEndpoint:
    if policy.target is None:
        raise ReplayDomainError(
            code="LUMORA-REPLAY-GUARD-001",
            message="Protocol replay requires an explicitly configured target",
            remediation="Configure the target for this replay; never inherit it from the capture.",
            context={"target": None},
        )
    if not isinstance(policy.dry_run, bool):
        raise TypeError("protocol replay dry_run must be a boolean")
    assert policy.target is not None
    if policy.target not in policy.allowed_targets:
        raise ReplayDomainError(
            code="LUMORA-REPLAY-GUARD-002",
            message=f"Protocol replay target {policy.target} is not allowlisted",
            remediation="Add the explicit target to the protocol replay allowlist.",
            context={
                "target": str(policy.target),
                "allowlist": tuple(str(target) for target in policy.allowed_targets),
            },
        )
    return policy.target


def _validate_monotonic_order(events: tuple[EventEnvelope, ...]) -> None:
    for previous, current in pairwise(events):
        if current.monotonic_ns < previous.monotonic_ns:
            raise ReplayDomainError(
                code="LUMORA-REPLAY-TIME-001",
                message="Replay event stream is not monotonic",
                remediation="Restore the capture with events in persisted sequence order.",
                context={
                    "previous_monotonic_ns": previous.monotonic_ns,
                    "current_monotonic_ns": current.monotonic_ns,
                    "previous_event_id": previous.event_id,
                    "current_event_id": current.event_id,
                },
            )


def _validate_protocol_monotonic_order(datasets: tuple[ProtocolReplayDataset, ...]) -> None:
    for previous, current in pairwise(datasets):
        if current.monotonic_ns < previous.monotonic_ns:
            raise ReplayDomainError(
                code="LUMORA-REPLAY-TIME-002",
                message="Protocol replay dataset stream is not monotonic",
                remediation="Restore the capture with datasets in persisted sequence order.",
                context={
                    "previous_monotonic_ns": previous.monotonic_ns,
                    "current_monotonic_ns": current.monotonic_ns,
                },
            )


def _with_previous_dataset(
    datasets: tuple[ProtocolReplayDataset, ...],
) -> Iterable[tuple[ProtocolReplayDataset | None, ProtocolReplayDataset]]:
    previous: ProtocolReplayDataset | None = None
    for dataset in datasets:
        yield previous, dataset
        previous = dataset


def _with_previous(
    events: tuple[EventEnvelope, ...],
) -> Iterable[tuple[EventEnvelope | None, EventEnvelope]]:
    previous: EventEnvelope | None = None
    for event in events:
        yield previous, event
        previous = event


__all__: tuple[str, ...] = ()
