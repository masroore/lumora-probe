# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Tests for the Phase 08 structured HTTP error contract."""

from __future__ import annotations

import httpx
import pytest

from lumora_probe.core.errors import LumoraError
from lumora_probe.web.api import create_app
from lumora_probe.web.contracts import ErrorResponse


def test_error_response_maps_core_error() -> None:
    error = LumoraError(
        code="LUMORA-CORE-TEST-001",
        message="Capture is unavailable.",
        remediation="Check the capture directory.",
        context={"capture_id": "capture-123", "attempt": 2},
    )

    response = ErrorResponse.from_error(error, status=503, correlation_id="corr-123")

    assert response.model_dump() == {
        "status": 503,
        "code": "LUMORA-CORE-TEST-001",
        "message": "Capture is unavailable.",
        "remediation": "Check the capture directory.",
        "context": {"capture_id": "capture-123", "attempt": 2},
        "correlation_id": "corr-123",
    }


@pytest.mark.asyncio
async def test_lumora_error_handler_returns_structured_response() -> None:
    application = create_app()

    @application.get("/test-error")
    def raise_error() -> None:
        raise LumoraError(
            code="LUMORA-CORE-TEST-002",
            message="The test resource is unavailable.",
            remediation="Retry after correcting the test setup.",
            context={"resource": "test"},
        )

    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/test-error", headers={"X-Correlation-ID": "corr-456"})

    assert response.status_code == 500
    assert response.headers["X-Correlation-ID"] == "corr-456"
    assert response.json() == {
        "status": 500,
        "code": "LUMORA-CORE-TEST-002",
        "message": "The test resource is unavailable.",
        "remediation": "Retry after correcting the test setup.",
        "context": {"resource": "test"},
        "correlation_id": "corr-456",
    }
