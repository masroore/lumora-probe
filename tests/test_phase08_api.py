# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Tests for the Phase 08 REST API foundation."""

from __future__ import annotations

import httpx
import pytest

from lumora_probe.web.api import API_PREFIX, api_v1_router, create_app


def test_api_uses_stable_versioned_prefix() -> None:
    application = create_app()

    assert api_v1_router.prefix == API_PREFIX
    assert application.openapi()["info"]["title"] == "Lumora Probe"


@pytest.mark.asyncio
async def test_api_root_reports_version() -> None:
    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get(API_PREFIX)

    assert response.status_code == 200
    assert response.json() == {"version": "v1"}
