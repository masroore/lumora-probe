# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Shared live-update governor and WebSocket transport adapters."""

from __future__ import annotations

import asyncio
from collections import Counter, deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from lumora_probe.shared.events import (
    DEFAULT_EVENT_REGISTRY,
    EventEnvelope,
    EventPayloadRegistry,
)

from .resources import ResourceStore
from .security import SecurityPolicy

STREAM_VERSION = 1
DEFAULT_FLUSH_INTERVAL_SECONDS = 0.1
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 15.0
DEFAULT_IDLE_TIMEOUT_SECONDS = 60.0

TopicSubscription = frozenset[str]
ClientKind = Literal["json", "ui"]


class LiveEventSubscription(Protocol):
    """Queue subscription contract consumed by the web adapter."""

    async def get(self) -> EventEnvelope: ...

    def task_done(self) -> None: ...

    async def close(self) -> None: ...


class LiveEventSource(Protocol):
    """Minimal event-source contract injected into the web adapter."""

    ui_queue_size: int
    registry: EventPayloadRegistry

    async def subscribe(
        self,
        callback: Any = None,
        *,
        channel: str = "ui",
        queue_size: int | None = None,
    ) -> LiveEventSubscription: ...


class _NullSubscription:
    async def get(self) -> EventEnvelope:
        await asyncio.Future()
        raise AssertionError("unreachable")

    def task_done(self) -> None:
        return

    async def close(self) -> None:
        return


class NullEventSource:
    """No-op source used until application bootstrap injects the real event bus."""

    ui_queue_size = 1
    registry = DEFAULT_EVENT_REGISTRY

    async def subscribe(
        self,
        callback: Any = None,
        *,
        channel: str = "ui",
        queue_size: int | None = None,
    ) -> LiveEventSubscription:
        return _NullSubscription()


@dataclass(frozen=True, slots=True)
class LiveSettings:
    """Operational limits for the live-update transport."""

    flush_interval_seconds: float = DEFAULT_FLUSH_INTERVAL_SECONDS
    heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    idle_timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS
    stream_queue_size: int = 128
    ui_queue_size: int = 32
    history_size: int = 1_000
    timeline_cap: int = 50
    handshake_timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.flush_interval_seconds <= 0:
            raise ValueError("flush_interval_seconds must be positive")
        if self.heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")
        if self.idle_timeout_seconds <= self.heartbeat_interval_seconds:
            raise ValueError("idle_timeout_seconds must exceed heartbeat_interval_seconds")
        if self.stream_queue_size < 1 or self.ui_queue_size < 1:
            raise ValueError("live queue sizes must be positive")
        if self.history_size < 1 or self.timeline_cap < 1:
            raise ValueError("history_size and timeline_cap must be positive")
        if self.handshake_timeout_seconds <= 0:
            raise ValueError("handshake_timeout_seconds must be positive")


@dataclass(frozen=True, slots=True)
class StreamSubscription:
    """Topic and cursor selection for the canonical JSON stream."""

    topics: TopicSubscription = frozenset({"*"})
    since_sequence: int | None = None


@dataclass(frozen=True, slots=True)
class UiSubscription:
    """Mounted UI view and panels allowed to receive HTML fragments."""

    page: str = ""
    panels: frozenset[str] = frozenset()
    topics: TopicSubscription = frozenset()


@dataclass(slots=True)
class LiveClient:
    """Bounded queue and mutable subscription for one connected client."""

    client_id: str
    kind: ClientKind
    subscription: StreamSubscription | UiSubscription
    queue: asyncio.Queue[dict[str, Any]]
    dropped_count: int = 0
    dropped_sequences: list[int] = field(default_factory=list)
    counter_state: Counter[str] = field(default_factory=Counter)
    status_state: dict[str, dict[str, Any]] = field(default_factory=dict)
    timeline_state: deque[dict[str, Any]] = field(default_factory=deque)

    async def get(self) -> dict[str, Any]:
        return await self.queue.get()

    def task_done(self) -> None:
        self.queue.task_done()


class CoalescingGovernor:
    """One fixed-interval coalescing layer shared by both live endpoints."""

    KNOWN_PANELS = frozenset({"counters", "operations", "status", "timeline"})

    def __init__(
        self,
        *,
        bus: LiveEventSource,
        settings: LiveSettings | None = None,
        template_root: Path | None = None,
    ) -> None:
        self.bus = bus
        self.settings = settings or LiveSettings()
        root = template_root or Path(__file__).with_name("templates")
        self.environment = Environment(
            loader=FileSystemLoader(str(root)),
            autoescape=select_autoescape(("html", "xml")),
        )
        self._clients: dict[str, LiveClient] = {}
        self._pending: list[EventEnvelope] = []
        self._history: deque[EventEnvelope] = deque(maxlen=self.settings.history_size)
        self._flush_task: asyncio.Task[None] | None = None
        self._client_counter = 0
        self._stopped = False

    @property
    def clients(self) -> tuple[LiveClient, ...]:
        return tuple(self._clients.values())

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    async def start(self) -> None:
        if self._flush_task is not None and not self._flush_task.done():
            return
        self._stopped = False
        self._flush_task = asyncio.create_task(self._run(), name="lumora-live-governor")

    async def stop(self) -> None:
        self._stopped = True
        task = self._flush_task
        self._flush_task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._pending.clear()

    def register_stream(
        self,
        *,
        topics: Iterable[str] = ("*",),
        since_sequence: int | None = None,
    ) -> LiveClient:
        self._client_counter += 1
        client = LiveClient(
            client_id=f"live-{self._client_counter}",
            kind="json",
            subscription=StreamSubscription(_normalise_topics(topics), since_sequence),
            queue=asyncio.Queue(maxsize=self.settings.stream_queue_size),
        )
        self._clients[client.client_id] = client
        return client

    def register_ui(
        self,
        *,
        page: str = "",
        panels: Iterable[str] = (),
        topics: Iterable[str] = (),
    ) -> LiveClient:
        self._client_counter += 1
        active_panels = frozenset(panel.strip().casefold() for panel in panels if panel.strip())
        unknown = active_panels - self.KNOWN_PANELS
        if unknown:
            raise ValueError(f"unknown UI panels: {', '.join(sorted(unknown))}")
        client = LiveClient(
            client_id=f"live-{self._client_counter}",
            kind="ui",
            subscription=UiSubscription(page.strip(), active_panels, _normalise_topics(topics)),
            queue=asyncio.Queue(maxsize=self.settings.ui_queue_size),
        )
        self._clients[client.client_id] = client
        return client

    def unregister(self, client: LiveClient) -> None:
        self._clients.pop(client.client_id, None)

    async def refresh_associations(self, association_store: ResourceStore | None) -> None:
        """Fetch active associations and inject them into all UI clients' status state."""
        if association_store is None:
            return
        associations = await association_store.list("associations")
        for client in self._clients.values():
            if client.kind != "ui":
                continue
            keys_to_remove = [key for key in client.status_state if key.startswith("assoc:")]
            for key in keys_to_remove:
                del client.status_state[key]
            for assoc in associations:
                assoc_id = str(assoc.get("association_id", ""))
                client.status_state[f"assoc:{assoc_id}"] = {
                    "aggregate_id": assoc_id,
                    "event_name": "Association",
                    "severity": "info",
                    "sequence": None,
                }

    def update_stream(
        self,
        client: LiveClient,
        *,
        topics: Iterable[str],
        since_sequence: int | None = None,
    ) -> None:
        if client.kind != "json":
            raise ValueError("client is not a JSON stream client")
        client.subscription = StreamSubscription(_normalise_topics(topics), since_sequence)

    def update_ui(
        self,
        client: LiveClient,
        *,
        page: str,
        panels: Iterable[str],
        topics: Iterable[str],
    ) -> None:
        if client.kind != "ui":
            raise ValueError("client is not a UI client")
        active_panels = frozenset(panel.strip().casefold() for panel in panels if panel.strip())
        unknown = active_panels - self.KNOWN_PANELS
        if unknown:
            raise ValueError(f"unknown UI panels: {', '.join(sorted(unknown))}")
        previous = cast(UiSubscription, client.subscription)
        if (
            previous.page != page.strip()
            or previous.panels != active_panels
            or previous.topics != _normalise_topics(topics)
        ):
            client.counter_state.clear()
            client.status_state.clear()
            client.timeline_state.clear()
        client.subscription = UiSubscription(page.strip(), active_panels, _normalise_topics(topics))

    def enqueue_replay(self, client: LiveClient, *, since_sequence: int | None) -> None:
        if client.kind != "json" or since_sequence is None:
            return
        events = [
            event
            for event in self._history
            if event.sequence is not None
            and event.sequence > since_sequence
            and _matches_topics(event, client.subscription.topics, self.bus)
        ]
        if events:
            self._enqueue(
                client,
                {
                    "type": "events",
                    "version": STREAM_VERSION,
                    "replayed": True,
                    "events": [_event_json(event) for event in events],
                    "dropped_count": 0,
                    "source_sequences": [
                        event.sequence for event in events if event.sequence is not None
                    ],
                },
            )

    async def publish(self, event: EventEnvelope) -> None:
        self._history.append(event)
        self._pending.append(event)

    async def flush_now(self) -> None:
        if not self._pending:
            return
        events = self._pending
        self._pending = []
        render_cache: dict[tuple[str, str, str], str] = {}
        for client in self.clients:
            if client.kind == "json":
                self._flush_json(client, events)
            else:
                self._flush_ui(client, events, render_cache)

    async def _run(self) -> None:
        while not self._stopped:
            await asyncio.sleep(self.settings.flush_interval_seconds)
            await self.flush_now()

    def _flush_json(self, client: LiveClient, events: list[EventEnvelope]) -> None:
        subscription = client.subscription
        assert isinstance(subscription, StreamSubscription)
        topics = _normalise_topics(subscription.topics)
        category_cache: dict[tuple[str, int], str | None] = {}
        matching = [
            event for event in events if _matches_topic_set(event, topics, self.bus, category_cache)
        ]
        if not matching:
            return
        self._enqueue(
            client,
            {
                "type": "events",
                "version": STREAM_VERSION,
                "replayed": False,
                "events": [_event_json(event) for event in matching],
                "dropped_count": 0,
                "source_sequences": [
                    event.sequence for event in matching if event.sequence is not None
                ],
            },
        )

    def _flush_ui(
        self,
        client: LiveClient,
        events: list[EventEnvelope],
        render_cache: dict[tuple[str, str, str], str],
    ) -> None:
        subscription = client.subscription
        assert isinstance(subscription, UiSubscription)
        topics = _normalise_topics(subscription.topics)
        category_cache: dict[tuple[str, int], str | None] = {}
        matching = [
            event
            for event in events
            if subscription.panels and _matches_topic_set(event, topics, self.bus, category_cache)
        ]
        if not matching:
            return
        state = _update_client_panel_state(client, matching, self.settings.timeline_cap, self.bus)
        fragments: list[dict[str, str]] = []
        for panel in sorted(subscription.panels):
            cache_key = (panel, subscription.page, repr(state[panel]))
            html = render_cache.get(cache_key)
            if html is None:
                html = self.render_panel(panel, subscription.page, state)
                render_cache[cache_key] = html
            fragments.append(
                {
                    "panel": panel,
                    "target": f"#panel-{panel}",
                    "html": html,
                }
            )
        self._enqueue(
            client,
            {
                "type": "fragments",
                "version": STREAM_VERSION,
                "page": subscription.page,
                "fragments": fragments,
                "dropped_count": 0,
                "source_sequences": [
                    event.sequence for event in matching if event.sequence is not None
                ],
            },
        )

    def render_panel(self, panel: str, page: str, state: Mapping[str, Any]) -> str:
        template = self.environment.get_template(f"partials/{panel}.html")
        return template.render(page=page, panel=panel, **state[panel])

    @staticmethod
    def _enqueue(client: LiveClient, message: dict[str, Any]) -> None:
        if client.queue.full():
            dropped = client.queue.get_nowait()
            client.queue.task_done()
            client.dropped_count += 1
            for sequence in dropped.get("source_sequences", []):
                if isinstance(sequence, int):
                    client.dropped_sequences.append(sequence)
        message["dropped_count"] = client.dropped_count
        if client.dropped_sequences:
            message["dropped_sequences"] = list(client.dropped_sequences)
            client.dropped_count = 0
            client.dropped_sequences.clear()
        client.queue.put_nowait(message)


class LiveUpdateHub:
    """Own one bus subscription and feed it into the shared governor."""

    def __init__(self, *, bus: LiveEventSource, governor: CoalescingGovernor) -> None:
        self.bus = bus
        self.governor = governor
        self._subscription: LiveEventSubscription | None = None
        self._pump_task: asyncio.Task[None] | None = None
        self._lifecycle_lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lifecycle_lock:
            if self._pump_task is not None and not self._pump_task.done():
                return
            self._subscription = await self.bus.subscribe(
                channel="ui",
                queue_size=self.bus.ui_queue_size,
            )
            await self.governor.start()
            self._pump_task = asyncio.create_task(self._pump(), name="lumora-live-bus-pump")

    async def stop(self) -> None:
        async with self._lifecycle_lock:
            task = self._pump_task
            self._pump_task = None
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            if self._subscription is not None:
                await self._subscription.close()
                self._subscription = None
            await self.governor.stop()

    async def _pump(self) -> None:
        assert self._subscription is not None
        while True:
            event = await self._subscription.get()
            self._subscription.task_done()
            await self.governor.publish(event)


def create_live_router(
    *,
    hub: LiveUpdateHub,
    security_policy: SecurityPolicy,
    settings: LiveSettings,
) -> APIRouter:
    """Create both live endpoints and the shared first-paint partial route."""

    router = APIRouter(tags=["live"])

    @router.websocket("/api/v1/events/stream")
    async def event_stream(websocket: WebSocket) -> None:  # pyright: ignore[reportUnusedFunction]
        if not await _accept_websocket(websocket, security_policy):
            return
        await hub.start()
        client = hub.governor.register_stream()
        await websocket.send_json(
            {
                "type": "ready",
                "version": STREAM_VERSION,
                "client_id": client.client_id,
                "resume": True,
                "topics": ["*"],
            }
        )
        await _serve_websocket(websocket, client, hub.governor, settings, kind="json")

    @router.websocket("/ws/ui")
    async def ui_stream(websocket: WebSocket) -> None:  # pyright: ignore[reportUnusedFunction]
        if not await _accept_websocket(websocket, security_policy):
            return
        await hub.start()
        client = hub.governor.register_ui()
        await websocket.send_json(
            {
                "type": "ready",
                "version": STREAM_VERSION,
                "client_id": client.client_id,
                "resume": True,
                "mounted": False,
            }
        )
        await _serve_websocket(websocket, client, hub.governor, settings, kind="ui")

    @router.get("/ui/partials/{panel}", include_in_schema=False)
    async def first_paint(panel: str, page: str = "") -> HTMLResponse:  # pyright: ignore[reportUnusedFunction]
        if panel not in CoalescingGovernor.KNOWN_PANELS:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Unknown panel")
        return HTMLResponse(
            hub.governor.render_panel(
                panel,
                page,
                _panel_state([], settings.timeline_cap, hub.bus),
            )
        )

    return router


async def _accept_websocket(websocket: WebSocket, policy: SecurityPolicy) -> bool:
    failure = policy.validate_websocket(
        host_header=websocket.headers.get("host", ""),
        client_host=websocket.client.host if websocket.client else "",
        origin=websocket.headers.get("origin"),
        forwarded_host=websocket.headers.get("x-forwarded-host"),
    )
    if failure is not None:
        await websocket.close(code=1008, reason=failure)
        return False
    await websocket.accept()
    return True


async def _serve_websocket(
    websocket: WebSocket,
    client: LiveClient,
    governor: CoalescingGovernor,
    settings: LiveSettings,
    *,
    kind: ClientKind,
) -> None:
    last_activity_ns = asyncio.get_running_loop().time() * 1_000_000_000

    async def receive_commands() -> None:
        nonlocal last_activity_ns
        try:
            while True:
                command = await websocket.receive_json()
                last_activity_ns = asyncio.get_running_loop().time() * 1_000_000_000
                if not isinstance(command, Mapping):
                    await websocket.send_json(_protocol_error("command must be an object"))
                    continue
                command_map = cast(Mapping[str, Any], command)
                version = command_map.get("version", STREAM_VERSION)
                if version != STREAM_VERSION:
                    await websocket.send_json(_protocol_error("unsupported protocol version"))
                    continue
                command_type = str(command_map.get("type", "")).casefold()
                if command_type in {"ping", "pong"}:
                    await websocket.send_json({"type": "pong", "version": STREAM_VERSION})
                elif (
                    command_type in {"subscribe", "resume"}
                    and kind == "json"
                    or command_type == "mount"
                    and kind == "ui"
                ):
                    try:
                        _apply_subscription_command(client, governor, command_map, kind)
                    except (TypeError, ValueError) as error:
                        await websocket.send_json(_protocol_error(str(error)))
                        continue
                    await websocket.send_json(_subscription_ack(client))
                else:
                    await websocket.send_json(_protocol_error("unsupported command"))
        except WebSocketDisconnect:
            return

    async def send_messages() -> None:
        try:
            while True:
                message = await client.get()
                client.task_done()
                await websocket.send_json(message)
        except WebSocketDisconnect:
            return

    async def heartbeat() -> None:
        nonlocal last_activity_ns
        try:
            while True:
                await asyncio.sleep(settings.heartbeat_interval_seconds)
                now_ns = asyncio.get_running_loop().time() * 1_000_000_000
                if now_ns - last_activity_ns >= settings.idle_timeout_seconds * 1_000_000_000:
                    await websocket.close(code=1000, reason="idle timeout")
                    return
                await websocket.send_json({"type": "ping", "version": STREAM_VERSION})
        except WebSocketDisconnect:
            return

    tasks = [
        asyncio.create_task(receive_commands(), name=f"{client.client_id}-receive"),
        asyncio.create_task(send_messages(), name=f"{client.client_id}-send"),
        asyncio.create_task(heartbeat(), name=f"{client.client_id}-heartbeat"),
    ]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        governor.unregister(client)


def _apply_subscription_command(
    client: LiveClient,
    governor: CoalescingGovernor,
    command: Mapping[str, Any],
    kind: ClientKind,
) -> None:
    topics = _string_values(command.get("topics", ("*",) if kind == "json" else ()))
    since_sequence = command.get("since_sequence")
    cursor = since_sequence if isinstance(since_sequence, int) and since_sequence >= 0 else None
    if kind == "json":
        governor.update_stream(client, topics=topics, since_sequence=cursor)
        governor.enqueue_replay(client, since_sequence=cursor)
        return
    panels = _string_values(command.get("panels", ()))
    page = str(command.get("page", ""))
    governor.update_ui(client, page=page, panels=panels, topics=topics)


def _subscription_ack(client: LiveClient) -> dict[str, Any]:
    if client.kind == "json":
        subscription = client.subscription
        assert isinstance(subscription, StreamSubscription)
        return {
            "type": "subscribed",
            "version": STREAM_VERSION,
            "topics": sorted(subscription.topics),
            "since_sequence": subscription.since_sequence,
        }
    subscription = client.subscription
    assert isinstance(subscription, UiSubscription)
    return {
        "type": "mounted",
        "version": STREAM_VERSION,
        "page": subscription.page,
        "panels": sorted(subscription.panels),
        "topics": sorted(subscription.topics),
    }


def _protocol_error(message: str) -> dict[str, Any]:
    return {
        "type": "error",
        "version": STREAM_VERSION,
        "code": "LUMORA-WS-PROTOCOL-001",
        "message": message,
        "remediation": "Send a supported subscription, mount, ping, or resume command.",
    }


def _normalise_topics(topics: Iterable[str]) -> TopicSubscription:
    return frozenset(topic.strip().casefold() for topic in topics if topic.strip())


def _string_values(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, Iterable):
        return ()
    values = cast(Iterable[Any], value)
    return tuple(item for item in values if isinstance(item, str))


def _matches_topics(event: EventEnvelope, topics: Iterable[str], bus: LiveEventSource) -> bool:
    normalised = _normalise_topics(topics)
    return _matches_topic_set(event, normalised, bus)


def _matches_topic_set(
    event: EventEnvelope,
    normalised: TopicSubscription,
    bus: LiveEventSource,
    category_cache: dict[tuple[str, int], str | None] | None = None,
) -> bool:
    if not normalised or "*" in normalised:
        return True
    cache_key = (event.event_name, event.event_version)
    if category_cache is not None and cache_key in category_cache:
        category_name = category_cache[cache_key]
    else:
        category = bus.registry.category_for(event.event_name, event.event_version)
        category_name = category.value.casefold() if category is not None else None
        if category_cache is not None:
            category_cache[cache_key] = category_name
    values = {event.event_name.casefold(), event.aggregate_type.casefold()}
    if category_name is not None:
        values.update({category_name, f"{category_name}s"})
    return bool(values & normalised)


def _event_json(event: EventEnvelope) -> dict[str, Any]:
    return event.model_dump(mode="json")


def _update_client_panel_state(
    client: LiveClient, events: Iterable[EventEnvelope], timeline_cap: int, bus: LiveEventSource
) -> dict[str, dict[str, Any]]:
    event_list = events if isinstance(events, list) else list(events)
    category_cache: dict[tuple[str, int], str | None] = {}
    previous_sequence = client.timeline_state[-1]["sequence"] if client.timeline_state else None
    ordered = previous_sequence is not None or not client.timeline_state
    for event in event_list:
        sequence = event.sequence
        if sequence is None or (previous_sequence is not None and sequence < previous_sequence):
            ordered = False
        if sequence is not None:
            previous_sequence = sequence

    for event in event_list:
        cache_key = (event.event_name, event.event_version)
        if cache_key not in category_cache:
            category = bus.registry.category_for(event.event_name, event.event_version)
            category_cache[cache_key] = category.value if category is not None else None
        category_name = category_cache[cache_key] or event.aggregate_type
        client.counter_state[f"category:{category_name}"] += 1
        client.counter_state[f"severity:{event.severity.value}"] += 1
        client.status_state[event.aggregate_id] = {
            "aggregate_id": event.aggregate_id,
            "aggregate_type": event.aggregate_type,
            "event_name": event.event_name,
            "severity": event.severity.value,
            "sequence": event.sequence,
        }
        client.timeline_state.append(
            {
                "event_name": event.event_name,
                "event_id": event.event_id,
                "sequence": event.sequence,
                "severity": event.severity.value,
            }
        )
        if ordered and len(client.timeline_state) > timeline_cap:
            client.timeline_state.popleft()
            client.counter_state["events_dropped"] += 1

    if not ordered:
        # Out-of-order events are uncommon; retain deterministic sequence ordering.
        sorted_timeline = sorted(client.timeline_state, key=lambda e: e["sequence"])
        client.timeline_state = deque(sorted_timeline)
        if len(client.timeline_state) > timeline_cap:
            dropped = len(client.timeline_state) - timeline_cap
            client.counter_state["events_dropped"] += dropped
            while len(client.timeline_state) > timeline_cap:
                client.timeline_state.popleft()
    return {
        "counters": {
            "counters": dict(sorted(client.counter_state.items())),
            "events_dropped": client.counter_state["events_dropped"],
        },
        "status": {"rows": tuple(client.status_state.values())},
        "timeline": {
            "events": tuple(client.timeline_state),
            "events_dropped": client.counter_state["events_dropped"],
        },
        "operations": {
            "rows": tuple(
                value
                for value in client.status_state.values()
                if value.get("aggregate_type") == "Operation"
            )
        },
    }


def _panel_state(
    events: Iterable[EventEnvelope], timeline_cap: int, bus: LiveEventSource
) -> dict[str, dict[str, Any]]:
    client = LiveClient(
        client_id="first-paint",
        kind="ui",
        subscription=UiSubscription(),
        queue=asyncio.Queue(maxsize=1),
    )
    return _update_client_panel_state(client, events, timeline_cap, bus)


__all__ = [
    "CoalescingGovernor",
    "LiveSettings",
    "LiveUpdateHub",
    "create_live_router",
]
