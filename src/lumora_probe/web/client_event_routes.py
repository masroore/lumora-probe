# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Dedicated, quarantined endpoint for client-asserted Viewer events."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from lumora_probe.core.errors import LumoraError
from lumora_probe.shared.events import (
    DEFAULT_EVENT_REGISTRY,
    EventCategory,
    EventEnvelope,
    EventOrigin,
    EventPayloadRegistry,
    EventSeverity,
)


class ClientEventRequest(BaseModel):
    """Client-supplied fields; producer and origin are intentionally absent."""

    model_config = ConfigDict(extra="forbid")

    event_name: str
    event_version: int = Field(ge=1)
    correlation_id: str | None = None
    aggregate_type: str = "Viewer"
    aggregate_id: str
    severity: EventSeverity = EventSeverity.INFO
    payload: dict[str, Any]


class WebEventClock(Protocol):
    """Injected wall and monotonic clock for event creation."""

    def now(self) -> datetime: ...

    def monotonic_ns(self) -> int: ...


class WebIdGenerator(Protocol):
    """Injected UUIDv7 identity source for event creation."""

    def new_id(self) -> str: ...


class ClientEventPublisher(Protocol):
    """Transport-neutral event publication contract."""

    async def publish(self, event: EventEnvelope) -> EventEnvelope: ...


@dataclass(slots=True)
class RateLimiter:
    """Fixed-window per-client limiter with deterministic injected limits."""

    limit: int = 60
    window_seconds: float = 60.0
    _requests: dict[str, deque[float]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.limit < 1 or self.window_seconds <= 0:
            raise ValueError("rate limiter requires a positive limit and window")
        self._requests = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = asyncio.get_running_loop().time()
        requests = self._requests[key]
        cutoff = now - self.window_seconds
        while requests and requests[0] <= cutoff:
            requests.popleft()
        if len(requests) >= self.limit:
            return False
        requests.append(now)
        return True


def create_client_event_router(
    *,
    publisher: ClientEventPublisher | None,
    clock: WebEventClock | None,
    id_generator: WebIdGenerator | None,
    registry: EventPayloadRegistry = DEFAULT_EVENT_REGISTRY,
    rate_limiter: RateLimiter | None = None,
) -> APIRouter:
    """Create the quarantined Viewer event endpoint."""

    limiter = rate_limiter or RateLimiter()
    router = APIRouter(prefix="/events", tags=["events"])

    @router.post("/client-asserted")
    async def publish_client_event(  # pyright: ignore[reportUnusedFunction]
        request: Request,
        event_request: ClientEventRequest,
    ) -> dict[str, Any]:
        if publisher is None or clock is None or id_generator is None:
            raise LumoraError(
                code="LUMORA-WEB-EVENTS-001",
                message="The event bus is not available.",
                remediation="Start the application event bus before asserting Viewer events.",
                context={},
            )
        client_key = request.client.host if request.client else "unknown"
        if not limiter.allow(client_key):
            raise LumoraError(
                code="LUMORA-WEB-RATE-001",
                message="Client-asserted event rate limit exceeded.",
                remediation="Retry after the rate-limit window expires.",
                context={"client": client_key, "limit": limiter.limit},
            )
        try:
            event = EventEnvelope.create(
                event_name=event_request.event_name,
                event_version=event_request.event_version,
                correlation_id=event_request.correlation_id,
                aggregate_type=event_request.aggregate_type,
                aggregate_id=event_request.aggregate_id,
                producer="web-ui",
                payload=event_request.payload,
                origin=EventOrigin.CLIENT_ASSERTED,
                clock=clock,
                id_generator=id_generator,
                severity=event_request.severity,
            )
            if (
                registry.category_for(event.event_name, event.event_version)
                is not EventCategory.VIEWER
            ):
                raise ValueError("client-asserted events must belong to the Viewer category")
            registry.validate(event)
        except (KeyError, TypeError, ValueError) as error:
            raise LumoraError(
                code="LUMORA-WEB-EVENTS-002",
                message="The client event is not a valid registered Viewer event.",
                remediation="Use a registered Viewer event name, version, and payload.",
                context={
                    "event_name": event_request.event_name,
                    "event_version": event_request.event_version,
                },
            ) from error
        published = await publisher.publish(event)
        return published.model_dump(mode="json")

    return router


__all__: tuple[str, ...] = ()
