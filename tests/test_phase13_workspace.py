# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

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


@pytest.mark.asyncio
async def test_workspace_renders_inline_ring_buffer_promotion_control() -> None:
    application = create_app(
        workspace_data={
            "study_instances": (
                {
                    "sop_instance_uid": "1.2.3",
                    "present_in_capture_count": 1,
                    "retention": {
                        "state": "retained",
                        "expires_at": "2026-07-30T00:05:00+00:00",
                        "promotion_start": "2026-07-30T00:00:00+00:00",
                        "promotion_end": "2026-07-30T00:01:00+00:00",
                        "aggregate_id": "association-1",
                        "promotable": True,
                    },
                },
            )
        }
    )
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "1.2.3" in response.text
    assert "retained" in response.text
    assert "Promote to capture" in response.text
    assert 'data-promotion-aggregate="association-1"' in response.text
    assert "/api/v1/captures/ring-buffer/promote" in response.text


@pytest.mark.asyncio
async def test_workspace_renders_metadata_inspector_actions_and_private_toggle() -> None:
    application = create_app(
        workspace_data={
            "metadata": {
                "tags": (
                    {
                        "tag": "(0010,0010)",
                        "keyword": "PatientName",
                        "vr": "PN",
                        "value": "Synthetic^Patient",
                        "private": False,
                    },
                ),
                "raw_dump": "(0010,0010) PN PatientName: Synthetic^Patient",
            }
        }
    )
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "Search tags or values" in response.text
    assert "Show private tags" in response.text
    assert "Copy JSON" in response.text
    assert "Copy raw" in response.text
    assert "Synthetic^Patient" in response.text
    assert "Raw dump" in response.text


@pytest.mark.asyncio
async def test_workspace_renders_cine_and_fullscreen_controls() -> None:
    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert 'id="cine-toggle"' in response.text
    assert 'aria-label="Toggle cine playback"' in response.text
    assert 'id="fullscreen-toggle"' in response.text
    assert 'aria-label="Toggle fullscreen viewer"' in response.text


@pytest.mark.asyncio
async def test_workspace_renders_command_palette_markup() -> None:
    """Command palette overlay, ARIA roles, and input are present in workspace HTML."""
    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "data-palette-overlay" in response.text
    assert 'role="dialog"' in response.text
    assert 'aria-modal="true"' in response.text
    assert "data-palette-input" in response.text
    assert 'role="combobox"' in response.text
    assert "data-palette-list" in response.text
    assert 'role="listbox"' in response.text
    assert "command-palette.js" in response.text
