"""Reusable read/query adapters for projection-backed REST collections."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .pagination import Page, PaginationParams, paginate
from .query import QueryError, QueryPolicy, apply_query, parse_filter, parse_sort
from .resources import InMemoryResourceStore, ResourceStore


def create_collection_router(
    *,
    resource: str,
    path: str,
    tag: str,
    policy: QueryPolicy,
    store: ResourceStore | None = None,
) -> APIRouter:
    """Create a list/retrieve router for one projection-backed collection."""

    resource_store = store or InMemoryResourceStore()
    router = APIRouter(prefix=path, tags=[tag])

    @router.get("")
    async def list_resource(  # pyright: ignore[reportUnusedFunction]
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=500),
        sort: str | None = None,
        filter: str | None = None,
    ) -> dict[str, object]:
        try:
            parse_sort(sort, policy)
            parse_filter(filter, policy)
            items, total = await resource_store.list_page(
                resource,
                offset=(page - 1) * page_size,
                limit=page_size,
                sort=sort,
                filter=filter,
            )
            return Page(items=tuple(items), page=page, page_size=page_size, total=total).as_dict()
        except QueryError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except (AttributeError, NotImplementedError):
            records = apply_query(
                await resource_store.list(resource),
                policy=policy,
                value_for=_mapping_value,
                sort=sort,
                filter=filter,
            )
        return paginate(records, PaginationParams(page=page, page_size=page_size)).as_dict()

    @router.get("/{resource_id}")
    async def get_resource(resource_id: str) -> Mapping[str, Any]:  # pyright: ignore[reportUnusedFunction]
        record = await resource_store.get(resource, resource_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"{tag.title()} not found")
        return record

    return router


def _mapping_value(item: Mapping[str, Any], field: str) -> Any:
    return item.get(field)


__all__: tuple[str, ...] = ()
