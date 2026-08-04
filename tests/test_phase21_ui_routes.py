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


@pytest.mark.asyncio
async def test_every_registered_route_renders_full_page_and_htmx_fragment() -> None:
    application = create_app()
    transport = httpx.ASGITransport(app=application)
    values = {
        "capture_id": "capture-1",
        "study_uid": "1.2.826.0.1.3680043.10.543.1",
        "instance_id": "instance-1",
        "operation_id": "operation-1",
        "plugin_id": "demo.plugin",
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        for route in UI_ROUTES:
            path = route.path
            for name in route.parameter_names:
                path = path.replace(f"{{{name}}}", values[name])
            full = await client.get(path)
            fragment = await client.get(path, headers={"HX-Request": "true"})
            assert full.status_code == 200, path
            assert "<!doctype html>" in full.text.lower(), path
            assert f'data-route-name="{route.name}"' in full.text, path
            assert fragment.status_code == 200, path
            assert "<!doctype html>" not in fragment.text.lower(), path
            assert 'id="workspace-view"' in fragment.text, path
            assert 'hx-swap-oob="true"' in fragment.text, path


@pytest.mark.asyncio
async def test_navigation_and_viewer_shell_follow_htmx_route_changes() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        full = await client.get("/captures")
        fragment = await client.get("/captures", headers={"HX-Request": "true"})

    assert 'data-route-name="captures" aria-current="page">Captures' in full.text
    assert 'class="explorer-item is-active" href="/captures"' in full.text
    assert 'class="workspace-panel viewer-panel"' in fragment.text
    assert 'id="viewer-heading"' in fragment.text


@pytest.mark.asyncio
async def test_contextual_route_owns_valid_tab_state() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        valid = await client.get("/captures/capture-1?tab=events")
        invalid = await client.get("/captures/capture-1?tab=unknown")

    assert 'id="tab-events" role="tab"' in valid.text
    assert (
        'id="tab-events" role="tab" href="?tab=events" aria-controls="panel-events" aria-selected="true"'
        in valid.text
    )
    assert (
        'id="tab-overview" role="tab" href="?tab=overview" aria-controls="panel-overview" aria-selected="true"'
        in invalid.text
    )


@pytest.mark.asyncio
async def test_workspace_interaction_inventory_passes() -> None:
    from lumora_probe.web.ui_actions import UI_ACTIONS
    from tests.ui_inventory import validate_interactions

    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/captures/capture-1?tab=events")

    validate_interactions(response.text, {action.name for action in UI_ACTIONS})


def test_interaction_inventory_rejects_inert_and_invalid_controls() -> None:
    from tests.ui_inventory import InventoryError, validate_interactions

    with pytest.raises(InventoryError, match="duplicate IDs"):
        validate_interactions('<div id="same"></div><div id="same"></div>', set())
    with pytest.raises(InventoryError, match="missing ARIA targets"):
        validate_interactions('<button aria-controls="missing" disabled>Open</button>', set())
    with pytest.raises(InventoryError, match="unowned visible controls"):
        validate_interactions('<button type="button">Does nothing</button>', set())
