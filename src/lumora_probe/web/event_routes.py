"""REST routes for the standing event resource."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .pagination import PaginationParams, paginate
from .query import QueryError, QueryPolicy, apply_query
from .resources import InMemoryResourceStore, ResourceStore

_EVENT_POLICY = QueryPolicy.from_fields(
    sort_fields=("sequence", "occurred_at", "event_name", "severity"),
    filter_fields=("event_id", "event_name", "correlation_id", "aggregate_id", "origin"),
)


def create_event_router(store: ResourceStore | None = None) -> APIRouter:
    """Create query routes for canonical event envelopes."""

    resource_store = store or InMemoryResourceStore()
    router = APIRouter(prefix="/events", tags=["events"])

    @router.get("")
    async def list_events(  # pyright: ignore[reportUnusedFunction]
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=500),
        sort: str | None = None,
        filter: str | None = None,
        correlation_id: str | None = None,
        sequence: int | None = Query(None, ge=0),
    ) -> dict[str, object]:
        events = await resource_store.list("events")
        if correlation_id is not None:
            events = tuple(
                event for event in events if event.get("correlation_id") == correlation_id
            )
        if sequence is not None:
            events = tuple(event for event in events if event.get("sequence") == sequence)
        try:
            events = apply_query(
                events,
                policy=_EVENT_POLICY,
                value_for=_mapping_value,
                sort=sort,
                filter=filter,
            )
        except QueryError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return paginate(events, PaginationParams(page=page, page_size=page_size)).as_dict()

    return router


def _mapping_value(item: Mapping[str, Any], field: str) -> Any:
    return item.get(field)


__all__: tuple[str, ...] = ()
