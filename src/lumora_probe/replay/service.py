# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Offline event replay into the loop-owned event bus."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable, Iterable, Mapping
from itertools import pairwise
from typing import Any, cast

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
    ReplayAuditStore,
    ReplayCancellation,
    ReplayCaptureProvider,
    ReplayJobContext,
    ReplayJobRegistry,
    ReplayOutcome,
    ReplayPreflight,
    ReplayRequest,
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
                    replay_id=run_replay_id,  # pyright: ignore[reportArgumentType]
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
                replay_id=run_replay_id,  # pyright: ignore[reportArgumentType]
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
                replay_id=run_replay_id,  # pyright: ignore[reportArgumentType]
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
        if self.clock is None or result.replay_id is None:  # pyright: ignore[reportUnnecessaryComparison]
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


class ReplayRuntime:
    """Compose protocol replay with durable jobs, audit, cancellation, and exclusivity."""

    def __init__(
        self,
        jobs: ReplayJobRegistry,
        *,
        sender_factory: Callable[[], DICOMDatasetSender],
        audit_store: ReplayAuditStore,
        clock: EventClock,
        exclusivity: InMemoryReplayExclusivity | None = None,
    ) -> None:
        self.jobs = jobs
        self.sender_factory = sender_factory
        self.audit_store = audit_store
        self.clock = clock
        self.exclusivity = exclusivity if exclusivity is not None else InMemoryReplayExclusivity()
        self._started = False

    async def startup(self) -> int:
        """Sweep persisted and in-memory jobs once when the application starts."""
        if self._started:
            return 0
        self._started = True
        return await self.jobs.startup_sweep(reason="process restarted")

    async def start_protocol_replay(
        self,
        datasets: Iterable[ProtocolReplayDataset],
        *,
        policy: ProtocolReplayPolicy,
        capture_fidelity: str,
        partial: bool = False,
        incomplete_aggregates: Iterable[str] = (),
        capture_id: str | None = None,
        speed: float = 1.0,
    ) -> Any:
        """Start a guarded protocol replay as a durable background operation."""
        source_datasets = tuple(datasets)
        parameters = {
            "capture_id": capture_id,
            "capture_fidelity": capture_fidelity,
            "partial": partial,
            "target": str(policy.target) if policy.target is not None else None,
            "dry_run": policy.dry_run,
            "planned_count": len(source_datasets),
        }

        async def worker(context: ReplayJobContext) -> str:
            audit_records: list[ProtocolReplayAuditRecord] = []

            def collect_audit(record: ProtocolReplayAuditRecord) -> None:
                audit_records.append(record)

            service = ProtocolReplayService(
                self.sender_factory(),
                policy=policy,
                audit_sink=collect_audit,
                clock=self.clock,
                exclusivity=self.exclusivity,
            )
            try:
                result = await service.replay(
                    source_datasets,
                    capture_fidelity=capture_fidelity,
                    partial=partial,
                    incomplete_aggregates=incomplete_aggregates,
                    replay_id=context.operation_id,
                    capture_id=capture_id,
                    cancellation=context.cancellation,
                    speed=speed,
                )
                await context.report_progress(
                    {
                        "planned": result.planned,
                        "attempted": result.count,
                        "confirmed": result.success_count,
                        "failed": result.failure_count,
                        "cancelled": result.cancelled,
                    }
                )
                return "cancelled" if result.cancelled else "completed"
            finally:
                for record in audit_records:
                    await self.audit_store.append_replay_audit(
                        {
                            "replay_id": record.replay_id,
                            "capture_id": record.capture_id,
                            "target": record.target,
                            "dry_run": record.dry_run,
                            "outcome": record.outcome,
                            "planned_count": record.planned_count,
                            "confirmed_count": record.confirmed_count,
                            "failed_count": record.failed_count,
                            "occurred_at": record.occurred_at,
                            "error": record.error,
                        }
                    )

        return await self.jobs.start("protocol-replay", worker, parameters=parameters)


class RuntimeReplayProvider:
    """Compose replay services with the shared operation/job infrastructure."""

    def __init__(
        self,
        *,
        operations: Any,
        jobs: Any,
        captures: ReplayCaptureProvider,
        publisher: Any,
        id_generator: Any,
        clock: Any,
        audit_store: Any,
        sender_factory: Any | None = None,
        allowed_targets: frozenset[Any] = frozenset(),
        read_only: bool = False,
    ) -> None:
        self.operations = operations
        self.jobs = jobs
        self.captures = captures
        self.publisher = publisher
        self.id_generator = id_generator
        self.clock = clock
        self.audit_store = audit_store
        self.sender_factory = sender_factory
        self.allowed_targets = allowed_targets
        self.read_only = read_only

    async def list(
        self, *, limit: int, cursor: int | None = None, state: str | None = None
    ) -> Mapping[str, Any]:
        page = await self.operations.list(
            limit=limit,
            cursor=cursor,
            state=state,
            job_type=None,
        )
        return {
            "items": tuple(
                item
                for item in page.get("items", ())
                if str(item.get("job_type", "")) in {"event-replay", "protocol-replay"}
            ),
            "next_cursor": page.get("next_cursor"),
        }

    async def get(self, operation_id: str) -> Mapping[str, Any] | None:
        record = await self.operations.get(operation_id)
        if record is None or str(record.get("job_type", "")) not in {
            "event-replay",
            "protocol-replay",
        }:
            return None
        return record

    async def preflight(self, request: ReplayRequest) -> ReplayPreflight:
        if self.read_only and request.mode.value == "protocol" and not request.dry_run:
            return ReplayPreflight(
                outcome=ReplayOutcome.REFUSED,
                request=request,
                reasons=("Server is in read-only mode.",),
                remediation=("Disable read-only mode before starting a protocol write.",),
            )
        capture = await self.captures.describe(request.capture_id)
        if capture is None:
            return ReplayPreflight(
                outcome=ReplayOutcome.REFUSED,
                request=request,
                reasons=("Capture was not found.",),
                remediation=("Select an existing capture before replaying.",),
            )
        fidelity = str(capture.get("fidelity", ""))
        planned_count = int(capture.get("event_count", capture.get("object_count", 0)) or 0)
        reasons: list[str] = []
        remediation: list[str] = []
        if request.mode.value == "event":
            if fidelity not in {"events", "protocol", "wire"}:
                reasons.append(f"Event replay is unavailable for capture fidelity {fidelity!r}.")
                remediation.append("Use a capture containing persisted events.")
        else:
            if fidelity not in {"protocol", "wire"}:
                reasons.append(f"Protocol replay is unavailable for capture fidelity {fidelity!r}.")
                remediation.append("Use a complete protocol or wire-fidelity capture.")
            if request.target is not None:
                target = NetworkEndpoint(request.target.host, request.target.port)
                if target not in self.allowed_targets:
                    reasons.append(f"Protocol replay target {target} is not allowlisted.")
                    remediation.append("Add the explicit target to the replay allowlist.")
            if bool(capture.get("partial", False)):
                reasons.append("Protocol replay cannot use a partial capture.")
                remediation.append("Promote a complete association window first.")
        return ReplayPreflight(
            outcome=ReplayOutcome.REFUSED if reasons else ReplayOutcome.ELIGIBLE,
            request=request,
            planned_count=planned_count,
            reasons=tuple(reasons),
            remediation=tuple(remediation),
        )

    async def create(self, request: ReplayRequest) -> Mapping[str, Any]:
        preflight = await self.preflight(request)
        if not preflight.eligible:
            raise ValueError("; ".join(preflight.reasons + preflight.remediation))
        if request.mode.value == "event":
            events = tuple(await self.captures.events(request.capture_id))

            async def worker(context: Any) -> str:
                result = await EventReplayService(
                    self.publisher,
                    id_generator=self.id_generator,
                ).replay(
                    events,
                    capture_id=request.capture_id,
                    replay_id=context.operation_id,
                    speed=request.speed,
                )
                await context.report_progress({"published": result.count, "planned": len(events)})
                return "completed"

            record = await self.jobs.start(
                "event-replay",
                worker,
                parameters=request.model_dump(mode="json"),
                progress_event_name="ReplayProgressed",
            )
        else:
            sender_factory = self.sender_factory
            if sender_factory is None:
                raise RuntimeError("Protocol replay sender is not configured")
            assert request.target is not None
            target = NetworkEndpoint(request.target.host, request.target.port)
            runtime = ReplayRuntime(
                self.jobs,
                sender_factory=lambda: sender_factory(target),
                audit_store=self.audit_store,
                clock=self.clock,
            )
            datasets = await self.captures.protocol_datasets(request.capture_id)
            record = await runtime.start_protocol_replay(
                datasets,
                policy=ProtocolReplayPolicy(
                    target=target,
                    allowed_targets=self.allowed_targets,
                    dry_run=request.dry_run,
                ),
                capture_fidelity=request.fidelity.value,
                partial=False,
                capture_id=request.capture_id,
                speed=request.speed,
            )
        return _record_mapping(record)

    async def cancel(self, operation_id: str) -> Mapping[str, Any] | None:
        record = await self.get(operation_id)
        if record is None or not bool(record.get("cancellable", False)):
            return None
        if not await self.operations.cancel(operation_id):
            return None
        return await self.get(operation_id) or {
            "operation_id": operation_id,
            "state": "cancellation_requested",
        }


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


def _record_mapping(record: Any) -> Mapping[str, Any]:
    if isinstance(record, Mapping):
        return dict(cast(Mapping[str, Any], record))
    return {
        "operation_id": record.operation_id,
        "job_type": record.job_type,
        "state": str(record.state),
        "parameters": dict(record.parameters),
        "progress": dict(getattr(record, "progress", {})),
        "cancellable": True,
    }


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
    if not isinstance(partial, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
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
    if not isinstance(policy.dry_run, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
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
