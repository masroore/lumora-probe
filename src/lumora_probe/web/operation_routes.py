"""REST routes for long-running operation progress."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException


class OperationRegistry(Protocol):
    """Read-side contract for the durable operation audit registry."""

    async def get(self, operation_id: str) -> Mapping[str, Any] | None: ...


class InMemoryOperationRegistry:
    """Deterministic registry double used until the app service is assembled."""

    def __init__(self, operations: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        self._operations = {key: dict(value) for key, value in (operations or {}).items()}

    async def get(self, operation_id: str) -> Mapping[str, Any] | None:
        operation = self._operations.get(operation_id)
        return dict(operation) if operation is not None else None


def create_operation_router(registry: OperationRegistry | None = None) -> APIRouter:
    """Create the operation progress endpoint."""

    operation_registry = registry or InMemoryOperationRegistry()
    router = APIRouter(prefix="/operations", tags=["operations"])

    @router.get("/{operation_id}")
    async def get_operation(operation_id: str) -> Mapping[str, Any]:  # pyright: ignore[reportUnusedFunction]
        operation = await operation_registry.get(operation_id)
        if operation is None:
            raise HTTPException(status_code=404, detail="Operation not found")
        return operation

    return router


__all__: tuple[str, ...] = ()
