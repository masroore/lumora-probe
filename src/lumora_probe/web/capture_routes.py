"""REST routes for capture resources."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .pagination import PaginationParams, paginate
from .query import QueryError, QueryPolicy, apply_query
from .resources import InMemoryResourceStore, ResourceStore

_CAPTURE_POLICY = QueryPolicy.from_fields(
    sort_fields=("capture_id", "created_at", "completed_at", "state", "fidelity"),
    filter_fields=("capture_id", "state", "fidelity", "source_root"),
)


def create_capture_router(store: ResourceStore | None = None) -> APIRouter:
    """Create capture routes against an injected resource store."""

    resource_store = store or InMemoryResourceStore()
    router = APIRouter(prefix="/captures", tags=["captures"])

    @router.get("")
    async def list_captures(  # pyright: ignore[reportUnusedFunction]
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=500),
        sort: str | None = None,
        filter: str | None = None,
    ) -> dict[str, object]:
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
