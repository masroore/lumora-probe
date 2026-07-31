"""Unified Search panel routes over existing projection and event contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Query

from .pagination import PaginationParams, paginate
from .resources import InMemoryResourceStore, ResourceStore

_SEARCH_KINDS = frozenset({"studies", "series", "instances", "events", "logs"})
_KIND_ID_FIELDS = {
    "studies": ("study_uid", "id"),
    "series": ("series_uid", "id"),
    "instances": ("sop_instance_uid", "id"),
    "events": ("event_id", "id"),
    "logs": ("id", "message"),
}


class LogSearchProvider(Protocol):
    """Optional operational-log surface for Search; never invents durable indexes."""

    async def list_logs(self) -> Sequence[Mapping[str, Any]]: ...


def create_search_router(
    *,
    projection_store: ResourceStore | None = None,
    event_store: ResourceStore | None = None,
    log_provider: LogSearchProvider | None = None,
) -> APIRouter:
    """Compose existing read contracts into incremental Search results."""

    projections = projection_store or InMemoryResourceStore()
    events = event_store or InMemoryResourceStore()
    router = APIRouter(prefix="/search", tags=["search"])

    @router.get("")
    async def search(  # pyright: ignore[reportUnusedFunction]
        q: str = Query("", max_length=256),
        kinds: str = Query("studies,series,instances,events,logs"),
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=200),
    ) -> dict[str, object]:
        selected = _parse_kinds(kinds)
        query = q.casefold().strip()
        rows: list[dict[str, Any]] = []
        if "studies" in selected:
            rows.extend(_match_rows(await projections.list("studies"), kind="studies", query=query))
        if "series" in selected:
            rows.extend(_match_rows(await projections.list("series"), kind="series", query=query))
        if "instances" in selected:
            rows.extend(
                _match_rows(await projections.list("instances"), kind="instances", query=query)
            )
        if "events" in selected:
            rows.extend(_match_rows(await events.list("events"), kind="events", query=query))
        if "logs" in selected:
            log_rows = await log_provider.list_logs() if log_provider is not None else ()
            rows.extend(_match_rows(tuple(log_rows), kind="logs", query=query))
        rows.sort(key=lambda item: (str(item["kind"]), str(item["label"]), str(item["id"])))
        return paginate(rows, PaginationParams(page=page, page_size=page_size)).as_dict()

    return router


def _parse_kinds(raw: str) -> frozenset[str]:
    parts = tuple(part.strip().casefold() for part in raw.split(",") if part.strip())
    if not parts:
        raise HTTPException(status_code=400, detail="kinds must name at least one search surface")
    unknown = sorted(set(parts) - _SEARCH_KINDS)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported search kinds: {', '.join(unknown)}",
        )
    return frozenset(parts)


def _match_rows(
    records: Sequence[Mapping[str, Any]],
    *,
    kind: str,
    query: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        label = _label_for(kind, record)
        identifier = _identifier_for(kind, record)
        haystack = " ".join(
            str(value)
            for value in (
                kind,
                identifier,
                label,
                record.get("study_uid"),
                record.get("series_uid"),
                record.get("sop_instance_uid"),
                record.get("event_name"),
                record.get("correlation_id"),
                record.get("message"),
                record.get("level"),
            )
            if value is not None
        ).casefold()
        if query and query not in haystack:
            continue
        rows.append(
            {
                "id": identifier,
                "kind": kind,
                "label": label,
                "study_uid": record.get("study_uid"),
                "series_uid": record.get("series_uid"),
                "sop_instance_uid": record.get("sop_instance_uid"),
                "event_name": record.get("event_name"),
                "sequence": record.get("sequence"),
                "message": record.get("message"),
            }
        )
    return rows


def _identifier_for(kind: str, record: Mapping[str, Any]) -> str:
    for field in _KIND_ID_FIELDS[kind]:
        value = record.get(field)
        if value is not None and str(value):
            return str(value)
    return f"{kind}:{hash(tuple(sorted((str(k), str(v)) for k, v in record.items())))}"


def _label_for(kind: str, record: Mapping[str, Any]) -> str:
    if kind == "studies":
        return str(record.get("study_uid") or "study")
    if kind == "series":
        return f"{record.get('study_uid')}/{record.get('series_uid')}"
    if kind == "instances":
        return str(record.get("sop_instance_uid") or "instance")
    if kind == "events":
        name = record.get("event_name") or "event"
        sequence = record.get("sequence")
        return f"{name}#{sequence}" if sequence is not None else str(name)
    return str(record.get("message") or record.get("id") or "log")


__all__ = ["LogSearchProvider", "create_search_router"]
