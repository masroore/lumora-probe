# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 25 responsive layout validation across desktop, tablet, and narrow viewports.

Tests that the workspace shell, primary navigation, panels, and operational grids
adapt correctly at each CSS breakpoint.  Runs without a real browser (ASGI transport).

Setup: none (no Playwright dependency).
Run:   uv run pytest -m component tests/test_phase25_responsive.py
"""

from __future__ import annotations

import re

import httpx
import pytest

from lumora_probe.web.api import create_app

NAV_LINKS = ["Dashboard", "Live Monitor", "Captures", "Studies", "Search", "Replay"]


# ---------------------------------------------------------------------------
# Shell structure present regardless of viewport
# ---------------------------------------------------------------------------


@pytest.mark.component
@pytest.mark.asyncio
async def test_workspace_shell_has_required_landmarks() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        resp = await client.get("/dashboard")
    assert resp.status_code == 200
    html = resp.text
    assert 'role="banner"' in html
    assert 'id="workspace-main"' in html
    assert 'aria-label="Primary navigation"' in html
    assert "<main" in html


@pytest.mark.component
@pytest.mark.asyncio
async def test_all_primary_nav_links_present() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        resp = await client.get("/dashboard")
    html = resp.text
    for label in NAV_LINKS:
        assert f">{label}</a>" in html, f"missing nav link: {label}"


@pytest.mark.component
@pytest.mark.asyncio
async def test_explorer_panel_and_toggle_present() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        resp = await client.get("/dashboard")
    html = resp.text
    assert 'id="explorer-panel"' in html
    assert 'data-panel-toggle="explorer"' in html
    assert "aria-expanded=" in html


# ---------------------------------------------------------------------------
# Responsive CSS rules: structural assertions
# ---------------------------------------------------------------------------


@pytest.mark.component
@pytest.mark.asyncio
async def test_operational_grid_collapses_at_narrow_width() -> None:
    """At <=800px the .operational-grid switches to single column."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        css = (await client.get("/static/css/app.css")).text
    assert re.search(r"@media\s*\(max-width:\s*800px\)", css), (
        "missing @media (max-width: 800px) rule"
    )


@pytest.mark.component
@pytest.mark.asyncio
async def test_primary_nav_wraps_at_tablet_width() -> None:
    """At <=980px the primary nav takes full width."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        css = (await client.get("/static/css/app.css")).text
    assert re.search(r"@media\s*\(max-width:\s*980px\)", css), (
        "missing @media (max-width: 980px) rule"
    )


@pytest.mark.component
@pytest.mark.asyncio
async def test_narrow_layout_hides_non_viewer_panel_bodies() -> None:
    """At <=700px panel bodies are hidden."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        css = (await client.get("/static/css/app.css")).text
    assert re.search(r"@media\s*\(max-width:\s*700px\)", css), (
        "missing @media (max-width: 700px) rule"
    )


# ---------------------------------------------------------------------------
# Every navigable view renders valid HTML with required data attributes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "route",
    [
        "/dashboard",
        "/live",
        "/captures",
        "/studies",
        "/search",
        "/replay",
        "/settings",
        "/plugins",
        "/audit",
    ],
)
@pytest.mark.component
@pytest.mark.asyncio
async def test_navigable_view_renders_with_workspace_frame(route: str) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        resp = await client.get(route)
    assert resp.status_code == 200
    html = resp.text
    assert "<!doctype html>" in html.lower() or "<!DOCTYPE html>" in html
    assert 'data-route-name="' in html, f"{route} missing data-route-name"
    assert 'id="workspace-view"' in html, f"{route} missing #workspace-view"


@pytest.mark.component
@pytest.mark.asyncio
async def test_captures_list_has_resource_table() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        resp = await client.get("/captures")
    html = resp.text
    assert "resource-table" in html or "table-wrap" in html


@pytest.mark.component
@pytest.mark.asyncio
async def test_studies_list_has_resource_table() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        resp = await client.get("/studies")
    html = resp.text
    assert "resource-table" in html or "table-wrap" in html


@pytest.mark.component
@pytest.mark.asyncio
async def test_search_has_query_form() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        resp = await client.get("/search")
    html = resp.text
    assert "data-search-input" in html or 'name="q"' in html
