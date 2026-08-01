# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Tests for the Phase 08 operation progress endpoint."""

from __future__ import annotations

import httpx
import pytest

from lumora_probe.web.api import create_app
from lumora_probe.web.operation_routes import InMemoryOperationRegistry


@pytest.mark.asyncio
async def test_operation_endpoint_exposes_progress_record() -> None:
    registry = InMemoryOperationRegistry(
        {"op-1": {"operation_id": "op-1", "state": "running", "progress": {"done": 2}}}
    )
    application = create_app(operation_registry=registry)
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/api/v1/operations/op-1")
        missing = await client.get("/api/v1/operations/missing")

    assert response.status_code == 200
    assert response.json()["progress"] == {"done": 2}
    assert missing.status_code == 404
