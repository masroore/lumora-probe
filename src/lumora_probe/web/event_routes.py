"""REST routes for the standing event resource."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from fastapi import APIRouter, HTTPException, Query

from .pagination import Page
from .query import QueryError, QueryPolicy, apply_query, parse_filter, parse_sort
from .resources import InMemoryResourceStore, ResourceStore

_EVENT_POLICY = QueryPolicy.from_fields(
    sort_fields=("sequence", "occurred_at", "event_name", "severity"),
    filter_fields=("event_id", "event_name", "correlation_id", "aggregate_id", "origin"),
)


@dataclass(frozen=True, slots=True)
class EventPageQuery:
    """Validated event page parameters passed to a server-side event adapter."""

    offset: int
    limit: int
    sort: str | None
    filter: str | None
    correlation_id: str | None
    sequence: int | None
    sequence_from: int | None
    sequence_to: int | None
    occurred_from: str | None
    occurred_to: str | None


@runtime_checkable
class EventPageStore(ResourceStore, Protocol):
    """Explicit server-side page contract for the standing event collection."""

    async def list_events_page(
        self, query: EventPageQuery
    ) -> tuple[tuple[Mapping[str, Any], ...], int]: ...


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
        sequence_from: int | None = Query(None, ge=0),
        sequence_to: int | None = Query(None, ge=0),
        occurred_from: str | None = None,
        occurred_to: str | None = None,
    ) -> dict[str, object]:
        if sequence_from is not None and sequence_to is not None and sequence_from > sequence_to:
            raise HTTPException(status_code=400, detail="sequence_from must not exceed sequence_to")
        try:
            parse_sort(sort, _EVENT_POLICY)
            parse_filter(filter, _EVENT_POLICY)
            query = EventPageQuery(
                offset=(page - 1) * page_size,
                limit=page_size,
                sort=sort,
                filter=filter,
                correlation_id=correlation_id,
                sequence=sequence,
                sequence_from=sequence_from,
                sequence_to=sequence_to,
                occurred_from=occurred_from,
                occurred_to=occurred_to,
            )
            if isinstance(resource_store, EventPageStore):
                events, total = await resource_store.list_events_page(query)
            else:
                events = await resource_store.list("events")
                events = filter_events(events, query)
                events = apply_query(
                    events,
                    policy=_EVENT_POLICY,
                    value_for=_mapping_value,
                    sort=sort,
                    filter=filter,
                )
                total = len(events)
                events = events[query.offset : query.offset + query.limit]
        except QueryError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return Page(items=tuple(events), page=page, page_size=page_size, total=total).as_dict()

    return router


def _mapping_value(item: Mapping[str, Any], field: str) -> Any:
    return item.get(field)


def _number_value(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else -1


def filter_events(
    events: Sequence[Mapping[str, Any]], query: EventPageQuery
) -> tuple[Mapping[str, Any], ...]:
    """Apply non-collection event predicates for the in-memory test adapter."""
    filtered = events
    if query.correlation_id is not None:
        filtered = tuple(item for item in filtered if item.get("correlation_id") == query.correlation_id)
    if query.sequence is not None:
        filtered = tuple(item for item in filtered if item.get("sequence") == query.sequence)
    if query.sequence_from is not None:
        filtered = tuple(
            item for item in filtered if _number_value(item.get("sequence")) >= query.sequence_from
        )
    if query.sequence_to is not None:
        filtered = tuple(
            item for item in filtered if _number_value(item.get("sequence")) <= query.sequence_to
        )
    if query.occurred_from is not None:
        filtered = tuple(
            item for item in filtered if str(item.get("occurred_at", "")) >= query.occurred_from
        )
    if query.occurred_to is not None:
        filtered = tuple(
            item for item in filtered if str(item.get("occurred_at", "")) <= query.occurred_to
        )
    return tuple(filtered)


__all__: tuple[str, ...] = ()
