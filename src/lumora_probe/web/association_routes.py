"""REST routes for observed association pairs."""

from __future__ import annotations

from fastapi import APIRouter

from .collection_routes import create_collection_router
from .query import QueryPolicy
from .resources import ResourceStore

_ASSOCIATION_POLICY = QueryPolicy.from_fields(
    sort_fields=("association_id", "status", "started_at", "completed_at"),
    filter_fields=("association_id", "status", "calling_ae", "called_ae"),
)


def create_association_router(store: ResourceStore | None = None) -> APIRouter:
    """Create association-pair list/retrieve routes."""

    return create_collection_router(
        resource="associations",
        path="/associations",
        tag="associations",
        policy=_ASSOCIATION_POLICY,
        store=store,
    )


__all__: tuple[str, ...] = ()
