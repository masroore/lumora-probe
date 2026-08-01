# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Phase 13 normalized frame endpoint tests."""

from __future__ import annotations

import httpx
import pytest

from lumora_probe.studies.contracts import (
    DecodedFrame,
    DecodedFrameMetadata,
    DecodeFailure,
    DecodeFailureKind,
)
from lumora_probe.web.api import create_app
from lumora_probe.web.frame_routes import InMemoryFrameProvider

FRAME = DecodedFrame(
    pixels=b"\x01\x00\x02\x00",
    duration_ns=17,
    metadata=DecodedFrameMetadata(
        rows=1,
        columns=2,
        frame_number=0,
        frame_count=1,
        bits_allocated=16,
        pixel_representation=0,
        rescale_slope=1.0,
        rescale_intercept=0.0,
        suggested_window_center=1.5,
        suggested_window_width=1.0,
        photometric_interpretation="MONOCHROME2",
        transfer_syntax_uid="1.2.840.10008.1.2.1",
    ),
)


@pytest.mark.asyncio
async def test_frame_endpoint_serves_raw_uint16_and_sidecar() -> None:
    application = create_app(
        frame_provider=InMemoryFrameProvider({("instance-1", 0): FRAME}),
    )
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/api/v1/instances/instance-1/frames/0")
        metadata = await client.get("/api/v1/instances/instance-1/frames/0/metadata")

    assert response.status_code == 200
    assert response.content == FRAME.pixels
    assert response.headers["x-lumora-pixel-format"] == "uint16le"
    assert response.headers["x-lumora-decode-duration-ns"] == "17"
    assert metadata.status_code == 200
    assert metadata.json()["columns"] == 2


@pytest.mark.asyncio
async def test_frame_endpoint_explains_unsupported_transfer_syntax() -> None:
    failure = DecodeFailure(
        kind=DecodeFailureKind.UNSUPPORTED_TRANSFER_SYNTAX,
        message="The server has no decoder for this transfer syntax.",
        remediation="Install a codec.",
        context={"transfer_syntax": "1.2.3"},
    )
    application = create_app(frame_provider=InMemoryFrameProvider({("bad", 0): failure}))
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/api/v1/instances/bad/frames/0")

    assert response.status_code == 415
    assert response.json()["remediation"] == "Install a codec."
