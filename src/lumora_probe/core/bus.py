"""Loop-owned event bus with explicit ingress and split subscriber backpressure."""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import threading
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from lumora_probe.core.clock import Clock, SystemClock
from lumora_probe.core.ids import IdGenerator, UUIDv7Generator
from lumora_probe.shared.events import (
    DEFAULT_EVENT_REGISTRY,
    EventCategory,
    EventEnvelope,
    EventOrigin,
    EventPayloadRegistry,
    EventSeverity,
)

EventCallback = Callable[[EventEnvelope], Awaitable[None] | None]


class ThreadIngressError(RuntimeError):
    """Base error for a rejected or failed threaded event submission."""

    def __init__(self, message: str, *, category: str) -> None:
        super().__init__(message)
        self.category = category


class ThreadIngressNotStartedError(ThreadIngressError):
    def __init__(self) -> None:
        super().__init__("EventBus is not accepting threaded ingress", category="not-started")


class ThreadIngressShuttingDownError(ThreadIngressError):
    def __init__(self) -> None:
        super().__init__("EventBus is shutting down", category="shutting-down")


class ThreadIngressSaturatedError(ThreadIngressError):
    def __init__(self) -> None:
        super().__init__("EventBus threaded ingress capacity is saturated", category="saturated")


class ThreadIngressCancelledError(ThreadIngressError):
    def __init__(self) -> None:
        super().__init__("EventBus threaded ingress submission was cancelled", category="cancelled")


class ThreadIngressTimedOutError(ThreadIngressError):
    def __init__(self) -> None:
        super().__init__("EventBus threaded ingress submission timed out", category="timed-out")


@dataclass(frozen=True, slots=True)
class ThreadIngressSnapshot:
    """Lock-safe diagnostics for the bounded thread ingress."""

    capacity: int
    pending: int
    saturation_refusals: int
    completion_failures: int
    cancellations: int
    timeouts: int


class SubscriberChannel(StrEnum):
    """Backpressure policy selected for a subscriber."""

    CAPTURE = "capture"
    UI = "ui"


class EventIngress(Protocol):
    """Transport-neutral contract for local and future remote publishers."""

    async def publish(
        self, event: EventEnvelope, *, capture_id: str | None = None
    ) -> EventEnvelope:
        """Publish an event from the current asyncio context."""
        ...

    def publish_from_thread(
        self, event: EventEnvelope, *, capture_id: str | None = None
    ) -> concurrent.futures.Future[EventEnvelope]:
        """Publish an event from a non-event-loop thread."""
        ...


@dataclass(frozen=True, slots=True)
class SubscriberStats:
    """Immutable snapshot of subscriber diagnostics."""

    delivered: int
    events_dropped: int
    failures: int
    budget_breaches: int


@dataclass(slots=True)
class _IngressRequest:
    event: EventEnvelope
    capture_id: str | None
    result: asyncio.Future[EventEnvelope]


class EventSubscription:
    """A queue-backed subscription used by capture and UI consumers."""

    def __init__(
        self,
        bus: EventBus,
        *,
        subscription_id: str,
        channel: SubscriberChannel,
        callback: EventCallback | None,
        queue_size: int,
    ) -> None:
        self._bus = bus
        self.subscription_id = subscription_id
        self.channel = SubscriberChannel(channel)
        self.callback = callback
        self._queue: asyncio.Queue[EventEnvelope] = asyncio.Queue(maxsize=queue_size)
        self._closed = False
        self._delivered = 0
        self._events_dropped = 0
        self._failures = 0
        self._budget_breaches = 0

    @property
    def events_dropped(self) -> int:
        return self._events_dropped

    @property
    def closed(self) -> bool:
        return self._closed

    def stats(self) -> SubscriberStats:
        return SubscriberStats(
            delivered=self._delivered,
            events_dropped=self._events_dropped,
            failures=self._failures,
            budget_breaches=self._budget_breaches,
        )

    async def get(self) -> EventEnvelope:
        """Wait for the next queued event."""
        if self.callback is not None:
            raise RuntimeError("callback subscriptions do not expose a queue")
        return await self._queue.get()

    def get_nowait(self) -> EventEnvelope:
        """Return the next queued event without waiting."""
        if self.callback is not None:
            raise RuntimeError("callback subscriptions do not expose a queue")
        return self._queue.get_nowait()

    def task_done(self) -> None:
        self._queue.task_done()

    async def join(self) -> None:
        """Wait until every queued event has been delivered to this subscription."""
        await self._queue.join()

    async def close(self) -> None:
        await self._bus.unsubscribe(self)

    async def enqueue_capture(self, event: EventEnvelope) -> None:
        await self._queue.put(event)

    def enqueue_ui(self, event: EventEnvelope) -> None:
        if self._queue.full():
            self._queue.get_nowait()
            self._queue.task_done()
            self._events_dropped += 1
            self._bus.record_events_dropped(self, event)
        self._queue.put_nowait(event)

    async def deliver(self, event: EventEnvelope, budget_seconds: float) -> None:
        started = self._bus.clock.monotonic_ns()
        try:
            if self.callback is not None:
                result = self.callback(event)
                if inspect.isawaitable(result):
                    await result
            else:
                if self.channel is SubscriberChannel.UI:
                    self.enqueue_ui(event)
                else:
                    await self.enqueue_capture(event)
            self._delivered += 1
        except Exception:  # noqa: BLE001 - one subscriber must not stop the bus
            self._failures += 1
            self._bus.record_subscriber_failure(self, event)
        finally:
            elapsed = (self._bus.clock.monotonic_ns() - started) / 1_000_000_000
            if elapsed > budget_seconds:
                self._budget_breaches += 1
                self._bus.record_budget_breach(self, event, elapsed)

    def close_internal(self) -> None:
        self._closed = True


class EventBus:
    """The asyncio-loop-owned ordering authority for all domain events."""

    def __init__(
        self,
        *,
        ingress_capacity: int = 1024,
        subscriber_budget_seconds: float = 0.1,
        thread_ingress_capacity: int | None = None,
        ui_queue_size: int = 256,
        clock_anomaly_threshold_ns: int = 1_000_000_000,
        clock: Clock | None = None,
        id_generator: IdGenerator | None = None,
        registry: EventPayloadRegistry | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        if ingress_capacity < 1:
            raise ValueError("ingress_capacity must be positive")
        if thread_ingress_capacity is not None and thread_ingress_capacity < 1:
            raise ValueError("thread_ingress_capacity must be positive")
        if ui_queue_size < 1:
            raise ValueError("ui_queue_size must be positive")
        if subscriber_budget_seconds <= 0:
            raise ValueError("subscriber_budget_seconds must be positive")
        if clock_anomaly_threshold_ns < 0:
            raise ValueError("clock_anomaly_threshold_ns must not be negative")
        self.ingress_capacity = ingress_capacity
        self.thread_ingress_capacity = thread_ingress_capacity or ingress_capacity
        self.subscriber_budget_seconds = subscriber_budget_seconds
        self.ui_queue_size = ui_queue_size
        self.clock_anomaly_threshold_ns = clock_anomaly_threshold_ns
        self.clock = clock or SystemClock()
        self.id_generator = id_generator or UUIDv7Generator()
        self.registry = registry or DEFAULT_EVENT_REGISTRY
        self._loop = loop
        self._ingress_queue: asyncio.Queue[_IngressRequest] | None = None
        self._dispatch_task: asyncio.Task[None] | None = None
        self._accepting = False
        self._closing = False
        self._subscribers: dict[str, EventSubscription] = {}
        self._next_sequence: dict[str, int] = {}
        self._last_times: dict[str, tuple[datetime, int]] = {}
        self._diagnostic_guard = False
        self._diagnostics: list[EventEnvelope] = []
        self._subscription_counter = 0
        self._thread_ingress = threading.BoundedSemaphore(self.thread_ingress_capacity)
        self._thread_pending = 0
        self._thread_pending_lock = threading.Lock()
        self._thread_saturation_refusals = 0
        self._thread_completion_failures = 0
        self._thread_cancellations = 0
        self._thread_timeouts = 0

    @property
    def ingress(self) -> EventIngress:
        """Return the transport-neutral ingress contract."""
        return self

    @property
    def started(self) -> bool:
        return self._accepting

    @property
    def diagnostics(self) -> tuple[EventEnvelope, ...]:
        return tuple(self._diagnostics)

    async def start(self) -> None:
        """Start accepting events on the current event loop."""
        if self._accepting:
            return
        if self._closing:
            raise RuntimeError("EventBus has been stopped")
        running_loop = asyncio.get_running_loop()
        if self._loop is not None and self._loop is not running_loop:
            raise RuntimeError("EventBus must be owned by one asyncio event loop")
        self._loop = running_loop
        self._ingress_queue = asyncio.Queue(maxsize=self.ingress_capacity)
        self._accepting = True
        self._dispatch_task = asyncio.create_task(self._run(), name="lumora-event-bus")

    async def stop(self) -> None:
        """Stop ingress after draining all accepted events and close subscriptions."""
        if not self._accepting:
            return
        self._closing = True
        self._accepting = False
        assert self._ingress_queue is not None
        await self._ingress_queue.join()
        while self.pending_thread_submissions:
            await asyncio.sleep(0)
        assert self._dispatch_task is not None
        self._dispatch_task.cancel()
        try:
            await self._dispatch_task
        except asyncio.CancelledError:
            pass
        for subscription in tuple(self._subscribers.values()):
            subscription.close_internal()
        self._subscribers.clear()

    async def publish(
        self, event: EventEnvelope, *, capture_id: str | None = None
    ) -> EventEnvelope:
        """Enqueue an event and return the immutable, sequenced published envelope."""
        if self._closing:
            raise RuntimeError("EventBus is shutting down")
        if not self._accepting:
            await self.start()
        assert self._ingress_queue is not None
        loop = asyncio.get_running_loop()
        result: asyncio.Future[EventEnvelope] = loop.create_future()
        await self._ingress_queue.put(_IngressRequest(event, capture_id, result))
        return await result

    def publish_from_thread(
        self, event: EventEnvelope, *, capture_id: str | None = None
    ) -> concurrent.futures.Future[EventEnvelope]:
        """Cross the only thread boundary through ``call_soon_threadsafe``."""
        if self._closing:
            raise ThreadIngressShuttingDownError()
        if not self._accepting or self._loop is None:
            raise ThreadIngressNotStartedError()
        if not self._thread_ingress.acquire(blocking=False):
            with self._thread_pending_lock:
                self._thread_saturation_refusals += 1
            raise ThreadIngressSaturatedError()
        with self._thread_pending_lock:
            self._thread_pending += 1
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.publish(event, capture_id=capture_id), self._loop
            )
        except BaseException:
            self._release_thread_ingress(category="cancelled")
            raise
        future.add_done_callback(self._thread_future_done)
        return future

    def _thread_future_done(self, future: concurrent.futures.Future[EventEnvelope]) -> None:
        category = "completed"
        if future.cancelled():
            category = "cancelled"
        else:
            if future.exception() is not None:
                category = "failed"
        self._release_thread_ingress(category=category)

    @property
    def pending_thread_submissions(self) -> int:
        with self._thread_pending_lock:
            return self._thread_pending

    def _release_thread_ingress(self, *, category: str = "completed") -> None:
        self._thread_ingress.release()
        with self._thread_pending_lock:
            self._thread_pending -= 1
            if category == "failed":
                self._thread_completion_failures += 1
            elif category == "cancelled":
                self._thread_cancellations += 1

    def thread_ingress_snapshot(self) -> ThreadIngressSnapshot:
        with self._thread_pending_lock:
            return ThreadIngressSnapshot(
                capacity=self.thread_ingress_capacity,
                pending=self._thread_pending,
                saturation_refusals=self._thread_saturation_refusals,
                completion_failures=self._thread_completion_failures,
                cancellations=self._thread_cancellations,
                timeouts=self._thread_timeouts,
            )

    def record_thread_ingress_timeout(self) -> None:
        with self._thread_pending_lock:
            self._thread_timeouts += 1

    async def subscribe(
        self,
        callback: EventCallback | None = None,
        *,
        channel: SubscriberChannel = SubscriberChannel.CAPTURE,
        queue_size: int | None = None,
    ) -> EventSubscription:
        """Register a callback or queue subscription."""
        if self._closing:
            raise RuntimeError("EventBus is shutting down")
        if not self._accepting:
            await self.start()
        self._subscription_counter += 1
        subscription_id = f"subscriber-{self._subscription_counter}"
        active_channel = SubscriberChannel(channel)
        if queue_size is None:
            active_size = self.ui_queue_size if active_channel is SubscriberChannel.UI else 0
        else:
            active_size = queue_size
        if active_size < 0 or (active_size == 0 and active_channel is SubscriberChannel.UI):
            raise ValueError("queue_size must be positive for UI and non-negative for capture")
        subscription = EventSubscription(
            self,
            subscription_id=subscription_id,
            channel=active_channel,
            callback=callback,
            queue_size=active_size,
        )
        self._subscribers[subscription_id] = subscription
        return subscription

    async def unsubscribe(self, subscription: EventSubscription) -> None:
        self._subscribers.pop(subscription.subscription_id, None)
        subscription.close_internal()

    async def _run(self) -> None:
        assert self._ingress_queue is not None
        while True:
            request = await self._ingress_queue.get()
            try:
                published = await self._publish_one(request.event, request.capture_id)
                if not request.result.done():
                    request.result.set_result(published)
            except Exception as exc:  # noqa: BLE001 - isolate one ingress failure
                if not request.result.done():
                    request.result.set_exception(exc)
            finally:
                self._ingress_queue.task_done()

    async def _publish_one(
        self, event: EventEnvelope, capture_id: str | None, *, emit_diagnostics: bool = True
    ) -> EventEnvelope:
        self.registry.validate(event)
        category = self.registry.category_for(event.event_name, event.event_version)
        if event.origin is EventOrigin.CLIENT_ASSERTED and (
            category is not EventCategory.VIEWER or event.producer != "web-ui"
        ):
            raise ValueError(
                "client-asserted events must be registered Viewer events produced by web-ui"
            )
        sequence_key = capture_id or event.aggregate_id
        sequence = self._next_sequence.get(sequence_key, 0) + 1
        self._next_sequence[sequence_key] = sequence
        published = event.with_sequence(sequence)
        anomaly = self._clock_anomaly(sequence_key, published)
        await self._dispatch(published)
        if anomaly is not None and emit_diagnostics and not self._diagnostic_guard:
            self._diagnostic_guard = True
            try:
                diagnostic = EventEnvelope.create(
                    event_name="ClockAnomalyDetected",
                    event_version=1,
                    correlation_id=published.correlation_id,
                    causation_id=published.event_id,
                    aggregate_type="Capture",
                    aggregate_id=sequence_key,
                    producer="event-bus",
                    severity=EventSeverity.WARNING,
                    payload=anomaly,
                    origin=EventOrigin.OBSERVED,
                    clock=self.clock,
                    id_generator=self.id_generator,
                )
                diagnostic = await self._publish_one(
                    diagnostic, sequence_key, emit_diagnostics=False
                )
                self._diagnostics.append(diagnostic)
            finally:
                self._diagnostic_guard = False
        return published

    async def _dispatch(self, event: EventEnvelope) -> None:
        for subscription in tuple(self._subscribers.values()):
            if subscription.closed:
                continue
            if subscription.callback is None and subscription.channel is SubscriberChannel.UI:
                subscription.enqueue_ui(event)
                continue
            await subscription.deliver(event, self.subscriber_budget_seconds)

    def _clock_anomaly(self, sequence_key: str, event: EventEnvelope) -> Mapping[str, Any] | None:
        previous = self._last_times.get(sequence_key)
        self._last_times[sequence_key] = (event.occurred_at, event.monotonic_ns)
        if previous is None:
            return None
        previous_wall, previous_monotonic = previous
        wall_delta_ns = int((event.occurred_at - previous_wall).total_seconds() * 1_000_000_000)
        monotonic_delta_ns = event.monotonic_ns - previous_monotonic
        divergence_ns = abs(wall_delta_ns - monotonic_delta_ns)
        if divergence_ns <= self.clock_anomaly_threshold_ns:
            return None
        return {
            "previous_occurred_at": previous_wall.isoformat(),
            "occurred_at": event.occurred_at.isoformat(),
            "wall_delta_ns": wall_delta_ns,
            "monotonic_delta_ns": monotonic_delta_ns,
            "divergence_ns": divergence_ns,
            "threshold_ns": self.clock_anomaly_threshold_ns,
        }

    def record_subscriber_failure(
        self, subscription: EventSubscription, event: EventEnvelope
    ) -> None:
        self._diagnostics.append(
            self._diagnostic_event(
                "ErrorRaised",
                {
                    "source": "event-bus",
                    "kind": "subscriber-failure",
                    "subscription_id": subscription.subscription_id,
                    "event_id": event.event_id,
                },
                severity=EventSeverity.ERROR,
                causation_id=event.event_id,
            )
        )

    def record_events_dropped(self, subscription: EventSubscription, event: EventEnvelope) -> None:
        self._diagnostics.append(
            self._diagnostic_event(
                "EventsDropped",
                {
                    "source": "event-bus",
                    "subscription_id": subscription.subscription_id,
                    "dropped_count": subscription.events_dropped,
                    "dropped_event_id": event.event_id,
                    "dropped_sequence": event.sequence,
                },
                severity=EventSeverity.WARNING,
                causation_id=event.event_id,
            )
        )

    def record_budget_breach(
        self, subscription: EventSubscription, event: EventEnvelope, elapsed_seconds: float
    ) -> None:
        self._diagnostics.append(
            self._diagnostic_event(
                "WarningRaised",
                {
                    "source": "event-bus",
                    "kind": "subscriber-budget-breach",
                    "subscription_id": subscription.subscription_id,
                    "event_id": event.event_id,
                    "elapsed_seconds": elapsed_seconds,
                    "budget_seconds": self.subscriber_budget_seconds,
                },
                severity=EventSeverity.WARNING,
                causation_id=event.event_id,
            )
        )

    def _diagnostic_event(
        self,
        event_name: str,
        payload: Mapping[str, Any],
        *,
        severity: EventSeverity,
        causation_id: str,
    ) -> EventEnvelope:
        return EventEnvelope.create(
            event_name=event_name,
            event_version=1,
            correlation_id=self.id_generator.new_id(),
            causation_id=causation_id,
            aggregate_type="System",
            aggregate_id="event-bus",
            producer="event-bus",
            severity=severity,
            payload=payload,
            origin=EventOrigin.OBSERVED,
            clock=self.clock,
            id_generator=self.id_generator,
        )


__all__ = [
    "EventBus",
    "EventIngress",
    "EventSubscription",
    "SubscriberChannel",
    "SubscriberStats",
    "ThreadIngressCancelledError",
    "ThreadIngressError",
    "ThreadIngressNotStartedError",
    "ThreadIngressSaturatedError",
    "ThreadIngressShuttingDownError",
    "ThreadIngressSnapshot",
    "ThreadIngressTimedOutError",
]
