# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 25 packaging qualification — installed wheel and asset completeness.

Verifies:
- All committed static assets are present and non-empty
- No Node/npm dependency at runtime
- All UI routes render successfully
- OpenAPI artifact is valid

Run: uv run pytest -m component tests/test_phase25_packaging.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from lumora_probe.web.api import create_app

ROOT = Path(__file__).parents[1]


# ---------------------------------------------------------------------------
# Static asset presence
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_all_committed_static_assets_exist() -> None:
    from lumora_probe.web.workspace_routes import STATIC_ROOT

    assert (STATIC_ROOT / "css" / "app.css").exists()
    assert (STATIC_ROOT / "css" / "app.css").stat().st_size > 100

    expected_js = [
        "command-palette.js",
        "workspace-controller.js",
        "tabs-controller.js",
        "dialog-controller.js",
        "live-client.js",
        "cornerstone-renderer.js",
        "investigation-controller.js",
        "viewer.js",
    ]
    for js_name in expected_js:
        js_path = STATIC_ROOT / "js" / js_name
        assert js_path.exists(), f"missing: js/{js_name}"
        assert js_path.stat().st_size > 0, f"empty: js/{js_name}"


@pytest.mark.component
def test_vendor_assets_present() -> None:
    vendor = ROOT / "assets" / "vendor"
    assert vendor.exists()
    assert (vendor / "manifest.json").exists()
    assert (vendor / "htmx.min.js").exists()
    assert (vendor / "alpine.min.js").exists()
    assert (vendor / "chart.umd.min.js").exists()
    assert (vendor / "tabulator.min.js").exists()
    assert (vendor / "tabulator.min.css").exists()


@pytest.mark.component
def test_cornerstone_bundle_exists() -> None:
    from lumora_probe.web.workspace_routes import STATIC_ROOT

    cs = STATIC_ROOT / "js" / "cornerstone-renderer.js"
    assert cs.exists(), "Cornerstone renderer bundle not committed"
    size_kb = cs.stat().st_size / 1024
    assert size_kb > 10, f"Cornerstone bundle suspiciously small: {size_kb:.1f} KB"
    print(f"cornerstone-renderer.js: {size_kb:.1f} KB")


# ---------------------------------------------------------------------------
# No Node dependency at runtime
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_no_node_required_at_runtime() -> None:
    """Import and render a workspace route without Node on PATH."""
    script = ROOT / "tests" / "_packaging_smoke.py"
    env = os.environ.copy()
    env["PATH"] = ""
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"failed without Node: {result.stderr}"
    assert "OK" in result.stdout


# ---------------------------------------------------------------------------
# All UI routes render
# ---------------------------------------------------------------------------


@pytest.mark.component
@pytest.mark.asyncio
async def test_all_navigable_ui_routes_render() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        routes = [
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
        for route in routes:
            resp = await client.get(route)
            assert resp.status_code == 200, f"{route} returned {resp.status_code}"
            assert "Lumora Probe" in resp.text, f"{route} missing brand"


@pytest.mark.component
@pytest.mark.asyncio
async def test_contextual_ui_routes_render() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        routes = [
            "/captures/capture-pkg-1",
            "/studies/study-pkg-1",
            "/instances/instance-pkg-1",
            "/replay/operation-pkg-1",
            "/plugins/plugin-pkg-1",
            "/operations/operation-pkg-1",
            "/reports/operation-pkg-1",
        ]
        for route in routes:
            resp = await client.get(route)
            assert resp.status_code == 200, f"{route} returned {resp.status_code}"


# ---------------------------------------------------------------------------
# OpenAPI artifact
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_openapi_artifact_exists_and_is_valid_json() -> None:
    openapi_path = ROOT / "docs" / "generated" / "openapi-v1.json"
    assert openapi_path.exists(), "OpenAPI artifact not found"
    data = json.loads(openapi_path.read_text(encoding="utf-8"))
    assert "openapi" in data or "swagger" in data
    assert "paths" in data
    assert len(data["paths"]) > 10, "OpenAPI has too few paths"
