# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Phase 19 local-only page-load verification."""

from __future__ import annotations

import re

import httpx
import pytest

from lumora_probe.web.api import create_app


@pytest.mark.asyncio
async def test_workspace_page_load_has_no_external_asset_requests() -> None:
    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/")
        css = await client.get("/static/css/app.css")
        renderer = await client.get("/static/js/cornerstone-renderer.js")

    assert response.status_code == 200
    assert not re.search(r"(?:href|src)=[\"'](?:https?:)?//", response.text, re.IGNORECASE)
    assert "/static/css/app.css" in response.text
    assert "/static/vendor/" in response.text
    assert css.status_code == 200
    assert renderer.status_code == 200
