# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 21 canonical browser route tests."""

from __future__ import annotations

import httpx
import pytest

from lumora_probe.web.api import create_app
from lumora_probe.web.ui_navigation import UI_ROUTES, NavigationGroup, routes_for


@pytest.mark.unit
def test_ui_route_registry_has_unique_names_and_paths() -> None:
    assert len({route.name for route in UI_ROUTES}) == len(UI_ROUTES)
    assert len({route.path for route in UI_ROUTES}) == len(UI_ROUTES)
    assert [route.path for route in routes_for(NavigationGroup.PRIMARY)] == [
        "/dashboard",
        "/live",
        "/captures",
        "/studies",
        "/search",
        "/replay",
    ]
    assert [route.path for route in routes_for(NavigationGroup.UTILITY)] == [
        "/settings",
        "/plugins",
        "/audit",
    ]


@pytest.mark.asyncio
async def test_root_redirects_to_canonical_dashboard() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/")

    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard"
