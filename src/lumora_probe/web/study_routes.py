"""REST routes for study, series, and instance projections."""

from __future__ import annotations

from fastapi import APIRouter

from .collection_routes import create_collection_router
from .query import QueryPolicy
from .resources import ResourceStore

_PROJECTION_POLICIES = {
    "studies": QueryPolicy.from_fields(
        sort_fields=("study_uid", "first_seen_at", "last_seen_at", "instance_count"),
        filter_fields=("study_uid",),
    ),
    "series": QueryPolicy.from_fields(
        sort_fields=("study_uid", "series_uid", "first_seen_at", "last_seen_at", "instance_count"),
        filter_fields=("study_uid", "series_uid"),
    ),
    "instances": QueryPolicy.from_fields(
        sort_fields=("study_uid", "series_uid", "sop_instance_uid", "created_at"),
        filter_fields=("capture_id", "study_uid", "series_uid", "sop_instance_uid"),
    ),
}


def create_projection_routers(store: ResourceStore | None = None) -> tuple[APIRouter, ...]:
    """Create projection collection routers with one injected provider."""

    return tuple(
        create_collection_router(
            resource=resource,
            path=f"/{resource}",
            tag=resource,
            policy=policy,
            store=store,
        )
        for resource, policy in _PROJECTION_POLICIES.items()
    )


__all__: tuple[str, ...] = ()
