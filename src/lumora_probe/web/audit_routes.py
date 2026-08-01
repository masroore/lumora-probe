# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Read-only audit log endpoint for incident investigation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from fastapi import APIRouter, Query


class AuditProvider(Protocol):
    async def list(self, *, category: str | None = None, limit: int = 100) -> tuple[Any, ...]: ...


def create_audit_router(provider: AuditProvider | None = None) -> APIRouter:
    router = APIRouter(prefix="/audit", tags=["audit"])

    @router.get("")
    async def list_audit(  # pyright: ignore[reportUnusedFunction]
        category: str | None = None, limit: int = Query(100, ge=1, le=500)
    ) -> Mapping[str, Any]:
        if provider is None:
            return {"items": []}
        records = await provider.list(category=category, limit=limit)
        return {
            "items": [
                record.as_dict() if hasattr(record, "as_dict") else dict(record)
                for record in records
            ]
        }

    return router


__all__ = ["AuditProvider", "create_audit_router"]
