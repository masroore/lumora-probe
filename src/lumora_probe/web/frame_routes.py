"""Per-instance, per-frame normalized pixel endpoints."""

from __future__ import annotations

import json
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import JSONResponse

from lumora_probe.studies.contracts import DecodedFrame, DecodeFailure


class FrameProvider(Protocol):
    """Application composition boundary for decoded frames."""

    async def get_frame(
        self, instance_id: str, frame_number: int
    ) -> DecodedFrame | DecodeFailure | None: ...


class InMemoryFrameProvider:
    """Deterministic frame provider for API tests and local composition."""

    def __init__(self, frames: dict[tuple[str, int], DecodedFrame] | None = None) -> None:
        self.frames = dict(frames or {})

    async def get_frame(self, instance_id: str, frame_number: int) -> DecodedFrame | None:
        return self.frames.get((instance_id, frame_number))


def create_frame_router(provider: FrameProvider | None = None) -> APIRouter:
    """Create normalized 16-bit frame and sidecar endpoints."""

    router = APIRouter(prefix="/instances", tags=["instances"])
    frame_provider = provider

    async def resolve(instance_id: str, frame_number: int) -> DecodedFrame | DecodeFailure | None:
        if frame_provider is None:
            return None
        return await frame_provider.get_frame(instance_id, frame_number)

    def failure_response(failure: DecodeFailure) -> JSONResponse:
        status = 415 if failure.kind.value == "unsupported-transfer-syntax" else 422
        return JSONResponse(
            status_code=status,
            content={
                "code": f"LUMORA-DECODE-{failure.kind.value.upper().replace('-', '_')}",
                "message": failure.message,
                "remediation": failure.remediation,
                "context": dict(failure.context),
            },
        )

    @router.get("/{instance_id}/frames/{frame_number}", response_class=Response)
    async def get_frame(instance_id: str, frame_number: int) -> Response:  # pyright: ignore[reportUnusedFunction]
        if frame_number < 0:
            raise HTTPException(status_code=422, detail="frame_number must be non-negative")
        frame = await resolve(instance_id, frame_number)
        if frame is None:
            raise HTTPException(status_code=404, detail="Instance or frame not found")
        if isinstance(frame, DecodeFailure):
            return failure_response(frame)
        return Response(
            content=frame.pixels,
            media_type="application/octet-stream",
            headers={
                "X-Lumora-Pixel-Format": "uint16le",
                "X-Lumora-Frame-Metadata": json.dumps(
                    frame.metadata.as_dict(), separators=(",", ":")
                ),
                "X-Lumora-Decode-Duration-Ns": str(frame.duration_ns),
            },
        )

    @router.get("/{instance_id}/frames/{frame_number}/metadata")
    async def get_frame_metadata(instance_id: str, frame_number: int) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        if frame_number < 0:
            raise HTTPException(status_code=422, detail="frame_number must be non-negative")
        frame = await resolve(instance_id, frame_number)
        if frame is None:
            raise HTTPException(status_code=404, detail="Instance or frame not found")
        if isinstance(frame, DecodeFailure):
            return failure_response(frame)
        return {**frame.metadata.as_dict(), "duration_ns": frame.duration_ns}

    return router


__all__: tuple[str, ...] = ()
