# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""REST routes for capture-backed DICOM metadata inspection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from fastapi import APIRouter, HTTPException, Query

from lumora_probe.studies.contracts import MetadataInspection


class MetadataProvider(Protocol):
    """Application composition boundary for metadata inspection."""

    async def get_metadata(
        self,
        instance_id: str,
        *,
        include_private: bool = False,
        query: str | None = None,
    ) -> MetadataInspection | Mapping[str, object] | None: ...


def create_metadata_router(provider: MetadataProvider | None = None) -> APIRouter:
    """Create metadata inspector routes over an injected object source."""

    router = APIRouter(prefix="/instances", tags=["metadata"])

    @router.get("/{instance_id}/metadata")
    async def get_metadata(  # pyright: ignore[reportUnusedFunction]
        instance_id: str,
        include_private: bool = Query(False),
        query: str | None = Query(None, max_length=200),
    ) -> Mapping[str, object]:  # pyright: ignore[reportUnusedFunction]
        if provider is None:
            raise HTTPException(status_code=404, detail="Metadata provider is not configured")
        result = await provider.get_metadata(
            instance_id,
            include_private=include_private,
            query=query,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Instance not found")
        as_dict = getattr(result, "as_dict", None)
        if callable(as_dict):
            return as_dict()  # pyright: ignore[reportReturnType]
        return result  # pyright: ignore[reportReturnType]

    return router


__all__ = ["MetadataProvider", "create_metadata_router"]
