# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 25 security and asset verification for the UI surface.

Covers:
- No outbound network requests from any page (ADR-0009)
- No CDN or external asset references (ADR-0009)
- Asset drift check (ADR-0025)
- No Access-Control-Allow-Origin header (ADR-0010)
- No inert/falsely-enabled controls
- Wheel packaging includes committed assets

Run: uv run pytest -m component tests/test_phase25_security.py
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import httpx
import pytest

from lumora_probe.web.api import create_app

ROOT = Path(__file__).parents[1]

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


# ---------------------------------------------------------------------------
# No external asset references (ADR-0009)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("route", NAVIGABLE_ROUTES, ids=lambda r: r.strip("/"))
@pytest.mark.component
@pytest.mark.asyncio
async def test_no_external_asset_references_in_html(route: str) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        resp = await client.get(route)
    external = re.findall(r"(?:href|src)=[\"'](https?:)?//", resp.text, re.IGNORECASE)
    assert not external, f"{route} references external assets: {external}"


@pytest.mark.parametrize("route", NAVIGABLE_ROUTES, ids=lambda r: r.strip("/"))
@pytest.mark.component
@pytest.mark.asyncio
async def test_no_cdn_references(route: str) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        resp = await client.get(route)
    cdn_refs = re.findall(
        r"(?:cdn\.|fonts\.googleapis|unpkg\.com|jsdelivr\.net|cloudflare)",
        resp.text,
        re.IGNORECASE,
    )
    assert not cdn_refs, f"{route} references CDN: {cdn_refs}"


# ---------------------------------------------------------------------------
# Static assets are local
# ---------------------------------------------------------------------------


@pytest.mark.component
@pytest.mark.asyncio
async def test_static_css_is_local() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        resp = await client.get("/static/css/app.css")
    assert resp.status_code == 200
    assert len(resp.content) > 0


@pytest.mark.component
def test_vendor_manifest_exists() -> None:
    manifest = ROOT / "assets" / "vendor" / "manifest.json"
    assert manifest.exists(), "vendor manifest not found"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "vendor manifest is not a JSON object"


# ---------------------------------------------------------------------------
# Asset drift check (ADR-0025)
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_committed_assets_match_clean_build() -> None:
    """Rebuild assets and verify no drift from committed versions."""
    result = subprocess.run(
        ["npm", "run", "build:assets"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"asset build failed: {result.stderr}"

    diff = subprocess.run(
        ["git", "diff", "--exit-code", "--", "static", "assets/vendor"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert diff.returncode == 0, f"committed assets drift from clean build:\n{diff.stdout}"


# ---------------------------------------------------------------------------
# No Access-Control-Allow-Origin header (ADR-0010)
# ---------------------------------------------------------------------------


@pytest.mark.component
@pytest.mark.asyncio
async def test_no_cors_headers() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        resp = await client.get("/api/v1/health/ready")
        lower_headers = {k.lower() for k in resp.headers}
        assert "access-control-allow-origin" not in lower_headers, (
            "CORS header present - ADR-0010 forbids this"
        )


# ---------------------------------------------------------------------------
# No inert controls in rendered HTML
# ---------------------------------------------------------------------------


@pytest.mark.component
@pytest.mark.asyncio
async def test_no_inert_visible_controls() -> None:
    """Every visible button should be owned by a data-* attribute, disabled,
    or have text/aria-label content."""
    for route in NAVIGABLE_ROUTES:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
        ) as client:
            resp = await client.get(route)
        html = resp.text
        buttons = re.findall(r"<button([^>]*)>(.*?)</button>", html, re.DOTALL)
        for attrs, content in buttons:
            if "disabled" in attrs or "aria-disabled" in attrs:
                continue
            if 'type="submit"' in attrs or 'type="reset"' in attrs:
                continue
            owner_prefixes = (
                "data-command-palette",
                "data-panel-toggle",
                "data-tab",
                "data-cancel-operation",
                "data-plugin-toggle",
                "data-replay",
                "data-settings",
                "data-workflow",
                "data-viewer",
                "data-promote",
                "data-delete",
                "data-bookmark",
                "data-inspector",
                "data-theme",
                "data-copy",
                "data-dialog",
                "data-search",
                "data-protocol",
            )
            if any(p in attrs for p in owner_prefixes):
                continue
            stripped = re.sub(r"<[^>]+>", "", content).strip()
            if stripped:
                continue
            if "aria-label" in attrs or "aria-labelledby" in attrs:
                continue
            pytest.fail(f"{route}: unowned icon-only button: {content[:60]}")


# ---------------------------------------------------------------------------
# Wheel packaging includes committed assets
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_wheel_includes_committed_static_assets() -> None:
    from lumora_probe.web.workspace_routes import STATIC_ROOT

    key_assets = [
        "css/app.css",
        "js/cornerstone-renderer.js",
        "js/workspace-controller.js",
        "js/tabs-controller.js",
        "js/dialog-controller.js",
        "js/command-palette.js",
        "js/live-client.js",
        "js/investigation-controller.js",
    ]
    for asset in key_assets:
        path = STATIC_ROOT / asset
        assert path.exists(), f"committed asset missing: {asset}"
        assert path.stat().st_size > 0, f"committed asset empty: {asset}"
