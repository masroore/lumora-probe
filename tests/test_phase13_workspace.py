"""Focused tests for the Phase 13 workspace shell."""

from __future__ import annotations

import httpx
import pytest

from lumora_probe.web.api import API_PREFIX, create_app


@pytest.mark.asyncio
async def test_workspace_root_renders_accessible_shell_and_static_asset() -> None:
    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/")
        static_response = await client.get("/static/css/app.css")
        api_response = await client.get(API_PREFIX)

    assert response.status_code == 200
    assert '<main id="workspace-main"' in response.text
    assert 'aria-label="Primary navigation"' in response.text
    assert 'aria-labelledby="explorer-heading"' in response.text
    assert 'aria-labelledby="viewer-heading"' in response.text
    assert 'aria-labelledby="inspector-heading"' in response.text
    assert "Timeline" in response.text
    assert "Logs" in response.text
    assert "status-bar" in response.text
    assert static_response.status_code == 200
    assert api_response.status_code == 200
    assert api_response.json() == {"version": "v1"}


@pytest.mark.asyncio
async def test_workspace_data_is_optional_and_escaped() -> None:
    application = create_app(
        workspace_data={
            "title": "Capture <A>",
            "active_context": "Study & Series",
            "events_dropped": 3,
            "timeline": ({"sequence": 4, "label": "C-STORE", "detail": "observed"},),
        }
    )
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "Capture &lt;A&gt;" in response.text
    assert "Study &amp; Series" in response.text
    assert "Events dropped" in response.text
    assert ">3<" in response.text
    assert "C-STORE" in response.text
