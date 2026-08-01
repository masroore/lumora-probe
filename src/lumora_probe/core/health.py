"""Readiness and liveness reporting for the service boundary."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .lifecycle import ServiceHealth

HealthProbe = Callable[[], ServiceHealth | Awaitable[ServiceHealth]]


@dataclass(frozen=True, slots=True)
class HealthReport:
    ready: bool
    alive: bool
    services: tuple[ServiceHealth, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "alive": self.alive,
            "services": [
                {"name": item.name, "ready": item.ready, "alive": item.alive, "detail": item.detail}
                for item in self.services
            ],
        }


class HealthRegistry:
    """Collect independent health probes and aggregate readiness/liveness."""

    def __init__(self) -> None:
        self._probes: dict[str, HealthProbe] = {}

    def register(self, name: str, probe: HealthProbe) -> None:
        self._probes[name] = probe

    def unregister(self, name: str) -> None:
        self._probes.pop(name, None)

    async def check(self) -> HealthReport:
        results: list[ServiceHealth] = []
        for name, probe in self._probes.items():
            result = probe()
            health = await result if inspect.isawaitable(result) else result
            results.append(
                health
                if health.name == name
                else ServiceHealth(name, health.ready, health.alive, health.detail)
            )
        services = tuple(results)
        return HealthReport(
            ready=bool(services) and all(item.ready for item in services),
            alive=bool(services) and all(item.alive for item in services),
            services=services,
        )
