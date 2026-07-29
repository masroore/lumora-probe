"""Single-process service lifecycle with bounded, draining shutdown."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, TypeVar

from .errors import LifecycleError


class LifecycleState(StrEnum):
    NEW = "new"
    STARTING = "starting"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ServiceHealth:
    name: str
    ready: bool
    alive: bool
    detail: str | None = None


class Service(Protocol):
    """Lifecycle contract for loop tasks, workers, executors, and DICOM services."""

    name: str

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def health(self) -> ServiceHealth: ...


class Drainable(Protocol):
    async def stop_accepting(self) -> None: ...

    async def drain(self) -> None: ...

    async def flush(self) -> None: ...


@dataclass(slots=True)
class _RegisteredService:
    service: Service
    started: bool = False


class LifecycleManager:
    """Own ordered startup, reverse shutdown, and per-service health."""

    def __init__(self, *, shutdown_grace_seconds: float = 10.0) -> None:
        self._services: list[_RegisteredService] = []
        self._shutdown_grace_seconds = shutdown_grace_seconds
        self._state = LifecycleState.NEW

    @property
    def state(self) -> LifecycleState:
        return self._state

    def register(self, service: Service) -> None:
        if self._state is not LifecycleState.NEW:
            raise LifecycleError(
                code="LUMORA-CORE-LIFE-001",
                message="Cannot register a service after lifecycle startup",
                remediation="Register every service before calling start().",
                context={"service": service.name, "state": self._state.value},
            )
        self._services.append(_RegisteredService(service=service))

    async def start(self) -> None:
        if self._state is not LifecycleState.NEW:
            raise LifecycleError(
                code="LUMORA-CORE-LIFE-002",
                message=f"Cannot start lifecycle from {self._state.value}",
                remediation="Create a new lifecycle manager for a second run.",
                context={"state": self._state.value},
            )
        self._state = LifecycleState.STARTING
        current_service_name = "unknown"
        try:
            for registration in self._services:
                current_service_name = registration.service.name
                await registration.service.start()
                registration.started = True
            self._state = LifecycleState.RUNNING
        except Exception as exc:
            self._state = LifecycleState.FAILED
            await self._stop_started()
            if isinstance(exc, LifecycleError):
                raise
            raise LifecycleError(
                code="LUMORA-CORE-LIFE-003",
                message=f"Service startup failed: {type(exc).__name__}",
                remediation="Inspect the service error and restart after correcting its dependency.",
                context={"service": current_service_name},
            ) from exc

    async def shutdown(self, *, grace_seconds: float | None = None) -> None:
        if self._state in {LifecycleState.NEW, LifecycleState.STOPPED}:
            self._state = LifecycleState.STOPPED
            return
        self._state = LifecycleState.DRAINING
        timeout = grace_seconds if grace_seconds is not None else self._shutdown_grace_seconds
        try:
            async with asyncio.timeout(timeout):
                await self._call_optional("stop_accepting")
                await self._call_optional("drain")
                await self._call_optional("flush")
                await self._stop_started()
        except TimeoutError as exc:
            self._state = LifecycleState.FAILED
            raise LifecycleError(
                code="LUMORA-CORE-LIFE-004",
                message=f"Lifecycle shutdown exceeded {timeout:.3f}s grace period",
                remediation="Inspect the interrupted service and increase the grace period only if justified.",
                context={"grace_seconds": timeout},
            ) from exc
        except Exception:
            self._state = LifecycleState.FAILED
            raise
        else:
            self._state = LifecycleState.STOPPED

    async def health(self) -> tuple[ServiceHealth, ...]:
        results: list[ServiceHealth] = []
        for registration in self._services:
            if not registration.started:
                results.append(
                    ServiceHealth(
                        name=registration.service.name,
                        ready=False,
                        alive=False,
                        detail="not started",
                    )
                )
                continue
            result = registration.service.health()
            results.append(await result if inspect.isawaitable(result) else result)
        return tuple(results)

    async def _call_optional(self, method_name: str) -> None:
        for registration in self._services:
            if not registration.started:
                continue
            method = getattr(registration.service, method_name, None)
            if method is None:
                continue
            result = method()
            if inspect.isawaitable(result):
                await result

    async def _stop_started(self) -> None:
        for registration in reversed(self._services):
            if not registration.started:
                continue
            try:
                result = registration.service.stop()
                if inspect.isawaitable(result):
                    await result
            finally:
                registration.started = False


T = TypeVar("T")


class ExecutorPool:
    """Async facade over a bounded thread pool for blocking work."""

    def __init__(self, workers: int, *, thread_name_prefix: str = "lumora-worker") -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix=thread_name_prefix
        )
        self._closed = False

    async def run(self, function: Callable[..., T], *args: Any) -> T:
        if self._closed:
            raise LifecycleError(
                code="LUMORA-CORE-LIFE-005",
                message="Executor pool is closed",
                remediation="Submit work before lifecycle shutdown or create a new pool.",
                context={},
            )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, lambda: function(*args))

    async def shutdown(self, *, wait: bool = True) -> None:
        if self._closed:
            return
        self._closed = True
        await asyncio.to_thread(self._executor.shutdown, wait=wait, cancel_futures=not wait)
