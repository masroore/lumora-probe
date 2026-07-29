"""REST health and readiness endpoints."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from fastapi import APIRouter, HTTPException


class HealthProvider(Protocol):
    """Read-side health contract for the HTTP adapter."""

    async def check(self) -> Mapping[str, object]: ...


class InMemoryHealthProvider:
    """Healthy default used before runtime service probes are assembled."""

    def __init__(self, *, ready: bool = True, alive: bool = True) -> None:
        self.ready = ready
        self.alive = alive

    async def check(self) -> Mapping[str, object]:
        return {"ready": self.ready, "alive": self.alive, "services": []}


def create_health_router(provider: HealthProvider | None = None) -> APIRouter:
    """Create liveness, readiness, and combined health endpoints."""

    health_provider = provider or InMemoryHealthProvider()
    router = APIRouter(prefix="/health", tags=["health"])

    @router.get("")
    async def health() -> Mapping[str, object]:  # pyright: ignore[reportUnusedFunction]
        return await health_provider.check()

    @router.get("/live")
    async def liveness() -> Mapping[str, object]:  # pyright: ignore[reportUnusedFunction]
        report = await health_provider.check()
        if not report.get("alive", False):
            raise HTTPException(status_code=503, detail="Service is not alive")
        return report

    @router.get("/ready")
    async def readiness() -> Mapping[str, object]:  # pyright: ignore[reportUnusedFunction]
        report = await health_provider.check()
        if not report.get("ready", False):
            raise HTTPException(status_code=503, detail="Service is not ready")
        return report

    return router


__all__: tuple[str, ...] = ()
