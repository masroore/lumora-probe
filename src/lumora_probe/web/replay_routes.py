# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""REST contracts and routes for guarded event and protocol replay."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Query

from lumora_probe.replay.contracts import (
    ReplayCaptureProvider,
    ReplayOutcome,
    ReplayPreflight,
    ReplayRequest,
    ReplayTarget,
)


class ReplayProvider(Protocol):
    """Application-owned replay orchestration boundary."""

    async def list(
        self, *, limit: int, cursor: int | None = None, state: str | None = None
    ) -> Mapping[str, Any]: ...

    async def get(self, operation_id: str) -> Mapping[str, Any] | None: ...

    async def preflight(self, request: ReplayRequest) -> ReplayPreflight: ...

    async def create(self, request: ReplayRequest) -> Mapping[str, Any]: ...

    async def cancel(self, operation_id: str) -> Mapping[str, Any] | None: ...


class EmptyReplayProvider:
    """Safe provider used when replay runtime is not composed."""

    async def list(
        self, *, limit: int, cursor: int | None = None, state: str | None = None
    ) -> Mapping[str, Any]:
        del limit, cursor, state
        return {"items": (), "next_cursor": None}

    async def get(self, operation_id: str) -> Mapping[str, Any] | None:
        del operation_id
        return None

    async def preflight(self, request: ReplayRequest) -> ReplayPreflight:
        return ReplayPreflight(
            outcome=ReplayOutcome.REFUSED,
            request=request,
            reasons=("Replay runtime is not configured.",),
            remediation=("Configure the replay runtime before starting work.",),
        )

    async def create(self, request: ReplayRequest) -> Mapping[str, Any]:
        del request
        raise RuntimeError("Replay runtime is not configured")

    async def cancel(self, operation_id: str) -> Mapping[str, Any] | None:
        del operation_id
        return None


def create_replay_router(provider: ReplayProvider | None = None) -> APIRouter:
    """Create bounded replay list, preflight, create, detail, and cancel routes."""

    active = provider or EmptyReplayProvider()
    router = APIRouter(prefix="/replays", tags=["replays"])

    @router.get("")
    async def list_replays(  # pyright: ignore[reportUnusedFunction]
        limit: int = Query(100, ge=1, le=100),
        cursor: int | None = Query(None, ge=0),
        state: str | None = None,
    ) -> Mapping[str, Any]:
        return await active.list(limit=limit, cursor=cursor, state=state)

    @router.post("/preflight")
    async def preflight_replay(  # pyright: ignore[reportUnusedFunction]
        request: ReplayRequest,
    ) -> ReplayPreflight:
        return await active.preflight(request)

    @router.post("", status_code=202)
    async def create_replay(  # pyright: ignore[reportUnusedFunction]
        request: ReplayRequest,
    ) -> Mapping[str, Any]:
        preflight = await active.preflight(request)
        if not preflight.eligible:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Replay preflight refused",
                    "reasons": preflight.reasons,
                    "remediation": preflight.remediation,
                },
            )
        try:
            return await active.create(request)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.get("/{operation_id}")
    async def get_replay(  # pyright: ignore[reportUnusedFunction]
        operation_id: str,
    ) -> Mapping[str, Any]:
        record = await active.get(operation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Replay operation not found")
        return record

    @router.post("/{operation_id}/cancel")
    async def cancel_replay(  # pyright: ignore[reportUnusedFunction]
        operation_id: str,
    ) -> Mapping[str, Any]:
        record = await active.cancel(operation_id)
        if record is None:
            raise HTTPException(
                status_code=409,
                detail="Replay is not running or does not support cooperative cancellation",
            )
        return record

    return router


__all__ = [
    "EmptyReplayProvider",
    "ReplayCaptureProvider",
    "ReplayOutcome",
    "ReplayPreflight",
    "ReplayProvider",
    "ReplayRequest",
    "ReplayTarget",
    "create_replay_router",
]
