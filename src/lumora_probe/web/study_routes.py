# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""REST routes for study, series, and instance projections."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException

from .collection_routes import create_collection_router
from .query import QueryPolicy
from .resources import ResourceStore
from .retention import RingBufferRetentionMap, join_retention


class StudyBrowserProvider(Protocol):
    """Application provider for capture-scoped study browser evidence."""

    async def get_study_browser(self, study_uid: str) -> Mapping[str, Any] | None: ...


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
        sort_fields=("instance_id", "study_uid", "series_uid", "sop_instance_uid", "created_at"),
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


def create_study_browser_router(
    provider: StudyBrowserProvider | None = None,
    retention_map: RingBufferRetentionMap | None = None,
) -> APIRouter:
    """Expose provenance and live retention without making Study authoritative."""

    router = APIRouter(prefix="/studies", tags=["studies"])

    @router.get("/{study_uid}/browser")
    async def get_study_browser(study_uid: str) -> Mapping[str, Any]:  # pyright: ignore[reportUnusedFunction]
        if provider is None:
            raise HTTPException(status_code=404, detail="Study browser provider is not configured")
        result = await provider.get_study_browser(study_uid)
        if result is None:
            raise HTTPException(status_code=404, detail="Study not found")
        if retention_map is not None:
            result = join_retention(result, retention_map.retention_by_digest())
        return result

    return router
