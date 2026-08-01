"""REST routes for capture resources."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Query

from .pagination import Page, PaginationParams, paginate
from .query import QueryError, QueryPolicy, apply_query
from .resources import InMemoryResourceStore, ResourceStore

_CAPTURE_POLICY = QueryPolicy.from_fields(
    sort_fields=("capture_id", "created_at", "completed_at", "state", "fidelity"),
    filter_fields=("capture_id", "state", "fidelity", "source_root"),
)


class RetentionStateProvider(Protocol):
    """Protocol-like boundary for ring-buffer retention state."""

    def status(self) -> Any:
        """Return JSON-compatible retention state."""
        ...


def create_capture_router(
    store: ResourceStore | None = None,
    retention_provider: RetentionStateProvider | None = None,
) -> APIRouter:
    """Create capture routes against an injected resource store."""

    resource_store = store or InMemoryResourceStore()
    router = APIRouter(prefix="/captures", tags=["captures"])

    @router.get("/ring-buffer")
    async def get_ring_buffer_status() -> Mapping[str, Any]:  # pyright: ignore[reportUnusedFunction]
        if retention_provider is None:
            return {"enabled": False, "reason": "ring buffer service is not mounted"}
        status = retention_provider.status()
        as_dict = getattr(status, "as_dict", None)
        return as_dict() if callable(as_dict) else status

    @router.post("/ring-buffer/promote")
    async def promote_ring_buffer(payload: Mapping[str, Any]) -> Mapping[str, Any]:  # pyright: ignore[reportUnusedFunction]
        if retention_provider is None:
            raise HTTPException(status_code=409, detail="ring buffer service is not mounted")
        promote = getattr(retention_provider, "promote_window", None)
        if not callable(promote):
            raise HTTPException(status_code=409, detail="ring buffer promotion is not available")
        try:
            start = datetime.fromisoformat(str(payload["start"]))
            end = datetime.fromisoformat(str(payload["end"]))
            manifest = await promote(
                start=start,
                end=end,
                capture_id=payload.get("capture_id"),
                aggregate_id=payload.get("aggregate_id"),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(
                status_code=422, detail=f"invalid promotion request: {error}"
            ) from error
        as_dict = getattr(manifest, "model_dump", None)
        return as_dict(mode="json") if callable(as_dict) else {"capture_id": str(manifest)}

    @router.get("")
    async def list_captures(  # pyright: ignore[reportUnusedFunction]
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=500),
        sort: str | None = None,
        filter: str | None = None,
    ) -> dict[str, object]:
        page_loader = getattr(resource_store, "list_page", None)
        if callable(page_loader) and sort is None and filter is None:
            items, total = await page_loader(
                offset=(page - 1) * page_size,
                limit=page_size,
            )
            return Page(items=tuple(items), page=page, page_size=page_size, total=total).as_dict()
        try:
            records = await resource_store.list("captures")
            records = apply_query(
                records,
                policy=_CAPTURE_POLICY,
                value_for=_mapping_value,
                sort=sort,
                filter=filter,
            )
        except QueryError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return paginate(records, PaginationParams(page=page, page_size=page_size)).as_dict()

    @router.get("/{capture_id}")
    async def get_capture(capture_id: str) -> Mapping[str, Any]:  # pyright: ignore[reportUnusedFunction]
        record = await resource_store.get("captures", capture_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Capture not found")
        return record

    @router.delete("/{capture_id}")
    async def delete_capture(capture_id: str) -> dict[str, object]:  # pyright: ignore[reportUnusedFunction]
        deleted = await resource_store.delete("captures", capture_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Capture not found")
        return {"deleted": True, "capture_id": capture_id}

    return router


def _mapping_value(item: Mapping[str, Any], field: str) -> Any:
    return item.get(field)


__all__: tuple[str, ...] = ()
