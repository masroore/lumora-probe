# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""REST routes for long-running operation progress."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any, Protocol, cast

from fastapi import APIRouter, HTTPException, Query


class OperationRegistry(Protocol):
    """Read-side contract for the durable operation audit registry."""

    async def get(self, operation_id: str) -> Mapping[str, Any] | None: ...

    async def list(
        self,
        *,
        limit: int = 100,
        cursor: int | None = None,
        state: str | None = None,
        job_type: str | None = None,
    ) -> Mapping[str, Any]: ...

    async def cancel(self, operation_id: str) -> bool: ...


class InMemoryOperationRegistry:
    """Deterministic registry double used until the app service is assembled."""

    def __init__(self, operations: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        self._operations = {key: dict(value) for key, value in (operations or {}).items()}

    async def get(self, operation_id: str) -> Mapping[str, Any] | None:
        operation = self._operations.get(operation_id)
        return dict(operation) if operation is not None else None

    async def list(
        self,
        *,
        limit: int = 100,
        cursor: int | None = None,
        state: str | None = None,
        job_type: str | None = None,
    ) -> Mapping[str, Any]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        offset = cursor or 0
        items = [
            dict(operation)
            for operation in self._operations.values()
            if (state is None or str(operation.get("state", "")) == state)
            and (job_type is None or str(operation.get("job_type", "")) == job_type)
        ]
        items.sort(
            key=lambda item: (str(item.get("started_at", "")), str(item.get("operation_id", ""))),
            reverse=True,
        )
        page = items[offset : offset + limit]
        next_cursor = offset + len(page) if offset + len(page) < len(items) else None
        return {
            "items": page,
            "next_cursor": str(next_cursor) if next_cursor is not None else None,
        }

    async def cancel(self, operation_id: str) -> bool:
        operation = self._operations.get(operation_id)
        if operation is None or not bool(operation.get("cancellable", False)):
            return False
        operation["state"] = "cancelled"
        operation["cancellable"] = False
        return True


class CompositeOperationRegistry:
    """Expose live cooperative jobs with durable history as one read contract."""

    def __init__(self, primary: Any, fallback: Any) -> None:
        self.primary = primary
        self.fallback = fallback

    async def get(self, operation_id: str) -> Mapping[str, Any] | None:
        live = await self.primary.get(operation_id)
        if live is not None:
            return _operation_mapping(live, cancellable=True)
        durable = await self.fallback.get(operation_id)
        return _operation_mapping(durable, cancellable=False) if durable is not None else None

    async def list(
        self,
        *,
        limit: int = 100,
        cursor: int | None = None,
        state: str | None = None,
        job_type: str | None = None,
    ) -> Mapping[str, Any]:
        _validate_page(limit, cursor)
        live_page = await self.primary.list(limit=100, state=state, job_type=job_type)
        durable_page = await self.fallback.list(limit=100, state=state, job_type=job_type)
        by_id = {
            str(item["operation_id"]): dict(item)
            for page in (durable_page, live_page)
            for item in page.get("items", ())
        }
        items = list(by_id.values())
        items.sort(
            key=lambda item: (str(item.get("started_at", "")), str(item.get("operation_id", ""))),
            reverse=True,
        )
        offset = cursor or 0
        page = items[offset : offset + limit]
        next_cursor = offset + len(page) if offset + len(page) < len(items) else None
        return {"items": page, "next_cursor": str(next_cursor) if next_cursor is not None else None}

    async def cancel(self, operation_id: str) -> bool:
        return await self.primary.cancel(operation_id)


def _operation_mapping(value: Any, *, cancellable: bool) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        item = dict(cast(Mapping[str, Any], value))
        item.setdefault("cancellable", cancellable)
        return item
    return {
        "operation_id": value.operation_id,
        "job_type": value.job_type,
        "parameters": dict(value.parameters),
        "state": str(value.state),
        "started_at": value.started_at.isoformat(),
        "completed_at": value.completed_at.isoformat() if value.completed_at else None,
        "outcome": value.outcome,
        "progress": dict(value.progress),
        "interruption_reason": value.interruption_reason,
        "cancellable": cancellable and str(value.state) == "running",
    }


def _validate_page(limit: int, cursor: int | None) -> None:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if cursor is not None and cursor < 0:
        raise ValueError("cursor must be non-negative")


def create_operation_router(
    registry: OperationRegistry | None = None,
    *,
    audit_sink: Callable[[Mapping[str, Any]], Any] | None = None,
) -> APIRouter:
    """Create the operation progress endpoint."""

    operation_registry = registry or InMemoryOperationRegistry()
    router = APIRouter(prefix="/operations", tags=["operations"])

    @router.get("")
    async def list_operations(  # pyright: ignore[reportUnusedFunction]
        limit: int = Query(100, ge=1, le=100),
        cursor: int | None = Query(None, ge=0),
        state: str | None = None,
        type: str | None = Query(None, alias="type"),
    ) -> Mapping[str, Any]:
        return await operation_registry.list(
            limit=limit,
            cursor=cursor,
            state=state,
            job_type=type,
        )

    @router.get("/{operation_id}")
    async def get_operation(operation_id: str) -> Mapping[str, Any]:  # pyright: ignore[reportUnusedFunction]
        operation = _operation_mapping(
            await operation_registry.get(operation_id), cancellable=False
        )
        if operation is None:
            raise HTTPException(status_code=404, detail="Operation not found")
        return operation

    @router.post("/{operation_id}/cancel")
    async def cancel_operation(operation_id: str) -> Mapping[str, Any]:  # pyright: ignore[reportUnusedFunction]
        operation = _operation_mapping(
            await operation_registry.get(operation_id), cancellable=False
        )
        if operation is None:
            raise HTTPException(status_code=404, detail="Operation not found")
        if not bool(operation.get("cancellable", False)):
            raise HTTPException(
                status_code=409,
                detail="Operation is not running or does not support cooperative cancellation",
            )
        if not await operation_registry.cancel(operation_id):
            raise HTTPException(status_code=409, detail="Operation cancellation was refused")
        if audit_sink is not None:
            result = audit_sink(
                {
                    "action": "cancel",
                    "operation_id": operation_id,
                    "job_type": operation.get("job_type"),
                }
            )
            if inspect.isawaitable(result):
                await result
        updated = _operation_mapping(await operation_registry.get(operation_id), cancellable=False)
        return updated or {"operation_id": operation_id, "state": "cancellation_requested"}

    return router


__all__ = [
    "CompositeOperationRegistry",
    "InMemoryOperationRegistry",
    "OperationRegistry",
    "create_operation_router",
]
