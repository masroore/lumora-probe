# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 25 comprehensive interaction inventory for all server-rendered HTML views.

Validates every navigable and contextual view for:
- Duplicate element IDs
- Broken ARIA target references
- Unowned visible controls (buttons/inputs without data-* owner attributes)
- Missing skip links
- Heading hierarchy violations

Run: uv run pytest -m component tests/test_phase25_inventory.py
"""

from __future__ import annotations

import re

import httpx
import pytest

from lumora_probe.web.api import create_app
from tests.ui_inventory import validate_interactions

NAVIGABLE_ROUTES = [
    "/dashboard",
    "/live",
    "/captures",
    "/studies",
    "/search",
    "/replay",
    "/settings",
    "/plugins",
    "/audit",
]

CONTEXTUAL_ROUTES = [
    "/captures/capture-inv-1?tab=events",
    "/studies/study-inv-1?tab=instances",
    "/instances/instance-inv-1?tab=properties",
    "/replay/operation-inv-1",
    "/plugins/plugin-inv-1",
    "/operations/operation-inv-1",
    "/reports/operation-inv-1",
]


async def _fetch(route: str) -> str:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        resp = await client.get(route)
        assert resp.status_code == 200, f"{route} returned {resp.status_code}"
        return resp.text


# ---------------------------------------------------------------------------
# Duplicate IDs, ARIA targets, unowned controls
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("route", NAVIGABLE_ROUTES, ids=lambda r: r.strip("/"))
@pytest.mark.component
@pytest.mark.asyncio
async def test_navigable_view_interaction_inventory(route: str) -> None:
    html = await _fetch(route)
    validate_interactions(html, set())


@pytest.mark.parametrize("route", CONTEXTUAL_ROUTES, ids=lambda r: r.split("?")[0])
@pytest.mark.component
@pytest.mark.asyncio
async def test_contextual_view_interaction_inventory(route: str) -> None:
    html = await _fetch(route)
    validate_interactions(html, set())


# ---------------------------------------------------------------------------
# Skip link present
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("route", NAVIGABLE_ROUTES, ids=lambda r: r.strip("/"))
@pytest.mark.component
@pytest.mark.asyncio
async def test_skip_link_present(route: str) -> None:
    html = await _fetch(route)
    assert 'class="skip-link"' in html or "skip-link" in html, f"{route} missing skip link"
    assert 'href="#workspace-main"' in html, f"{route} skip link missing target"


# ---------------------------------------------------------------------------
# Heading hierarchy
# ---------------------------------------------------------------------------


def _headings(html: str) -> list[tuple[int, str]]:
    return [
        (int(m.group(1)), m.group(2).strip())
        for m in re.finditer(r"<h([1-6])[^>]*>(.*?)</h\1>", html, re.DOTALL)
    ]


@pytest.mark.parametrize("route", NAVIGABLE_ROUTES, ids=lambda r: r.strip("/"))
@pytest.mark.component
@pytest.mark.asyncio
async def test_heading_hierarchy_starts_at_h1(route: str) -> None:
    html = await _fetch(route)
    headings = _headings(html)
    assert headings, f"{route} has no headings"
    assert headings[0][0] == 1, f"{route} first heading is h{headings[0][0]}, expected h1"


@pytest.mark.parametrize("route", NAVIGABLE_ROUTES, ids=lambda r: r.strip("/"))
@pytest.mark.component
@pytest.mark.asyncio
async def test_heading_hierarchy_no_skipped_levels(route: str) -> None:
    html = await _fetch(route)
    headings = _headings(html)
    for i in range(1, len(headings)):
        prev_level, cur_level = headings[i - 1][0], headings[i][0]
        assert cur_level <= prev_level + 1, f"{route}: h{prev_level} -> h{cur_level} skips a level"


# ---------------------------------------------------------------------------
# No external asset references
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("route", NAVIGABLE_ROUTES, ids=lambda r: r.strip("/"))
@pytest.mark.component
@pytest.mark.asyncio
async def test_no_external_asset_references(route: str) -> None:
    html = await _fetch(route)
    external = re.findall(r"(?:href|src)=[\"'](https?:)?//", html, re.IGNORECASE)
    assert not external, f"{route} references external assets: {external}"


# ---------------------------------------------------------------------------
# ARIA landmark coverage
# ---------------------------------------------------------------------------


@pytest.mark.component
@pytest.mark.asyncio
async def test_all_views_have_main_landmark() -> None:
    for route in NAVIGABLE_ROUTES:
        html = await _fetch(route)
        assert "<main" in html, f"{route} missing <main> landmark"
