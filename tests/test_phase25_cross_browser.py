# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 25 cross-browser navigation, tabs, history, and deep-link Playwright suites.

Runs on Chromium, Firefox, and WebKit via pytest-playwright parameterisation.
Setup: uv run playwright install chromium firefox webkit
Run:   LUMORA_E2E=1 uv run pytest -m e2e tests/test_phase25_cross_browser.py
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator

import pytest
import uvicorn
from playwright.sync_api import Page, expect

from lumora_probe.web.api import create_app

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def ui_base_url() -> Iterator[str]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        thread.join(0.01)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


def test_dashboard_renders_and_navigation_is_client_side(page: Page, ui_base_url: str) -> None:
    external: list[str] = []
    page.on(
        "request",
        lambda request: (
            external.append(request.url) if not request.url.startswith(ui_base_url) else None
        ),
    )
    page.goto(f"{ui_base_url}/dashboard")
    expect(page).to_have_url(f"{ui_base_url}/dashboard")
    page.get_by_role("navigation", name="Primary navigation").get_by_role(
        "link", name="Captures", exact=True
    ).click()
    expect(page).to_have_url(f"{ui_base_url}/captures")
    expect(page.locator("#workspace-view")).to_have_attribute("data-route-name", "captures")
    assert external == [], f"unexpected external requests: {external}"


def test_primary_navigation_links_all_resolve(page: Page, ui_base_url: str) -> None:
    page.goto(f"{ui_base_url}/dashboard")
    nav = page.get_by_role("navigation", name="Primary navigation")
    links = nav.get_by_role("link").all()
    assert len(links) >= 6, f"expected >= 6 primary nav links, got {len(links)}"
    for link in links:
        href = link.get_attribute("href")
        assert href, f"nav link missing href: {link.inner_text()}"
        link.click()
        expect(page).to_have_url(f"{ui_base_url}{href}")


# ---------------------------------------------------------------------------
# History and deep links
# ---------------------------------------------------------------------------


def test_browser_back_restores_previous_route(page: Page, ui_base_url: str) -> None:
    page.goto(f"{ui_base_url}/dashboard")
    page.get_by_role("navigation", name="Primary navigation").get_by_role(
        "link", name="Studies"
    ).click()
    expect(page).to_have_url(f"{ui_base_url}/studies")
    page.go_back()
    expect(page).to_have_url(f"{ui_base_url}/dashboard")


def test_deep_link_capture_detail_tab(page: Page, ui_base_url: str) -> None:
    page.goto(f"{ui_base_url}/captures/capture-x?tab=events")
    expect(page).to_have_url(f"{ui_base_url}/captures/capture-x?tab=events")
    events_tab = page.get_by_role("tab", name="Events", exact=True)
    expect(events_tab).to_have_attribute("aria-selected", "true")


def test_deep_link_study_detail_tab(page: Page, ui_base_url: str) -> None:
    page.goto(f"{ui_base_url}/studies/study-x?tab=instances")
    expect(page).to_have_url(f"{ui_base_url}/studies/study-x?tab=instances")
    # Without real data the study renders an empty state; URL is the authority.
    expect(page.locator("#workspace-view")).to_have_attribute("data-route-name", "study-detail")


def test_deep_link_instance_detail_tab(page: Page, ui_base_url: str) -> None:
    page.goto(f"{ui_base_url}/instances/instance-x?tab=properties")
    expect(page).to_have_url(f"{ui_base_url}/instances/instance-x?tab=properties")
    expect(page.locator("#workspace-view")).to_have_attribute("data-route-name", "instance-detail")


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------


def test_context_tabs_keyboard_navigation_and_url_sync(page: Page, ui_base_url: str) -> None:
    page.goto(f"{ui_base_url}/captures/capture-1?tab=overview")
    overview = page.get_by_role("tab", name="Overview", exact=True).last
    events = page.get_by_role("tab", name="Events", exact=True).last
    overview.focus()
    page.keyboard.press("End")
    expect(page).to_have_url(f"{ui_base_url}/captures/capture-1?tab=report")
    expect(page.get_by_role("tab", name="Report", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    events.click()
    expect(page).to_have_url(f"{ui_base_url}/captures/capture-1?tab=events")
    page.reload()
    expect(page.get_by_role("tab", name="Events", exact=True).last).to_have_attribute(
        "aria-selected", "true"
    )


# ---------------------------------------------------------------------------
# Command palette
# ---------------------------------------------------------------------------


def test_command_palette_opens_and_navigates(page: Page, ui_base_url: str) -> None:
    page.goto(f"{ui_base_url}/dashboard")
    page.keyboard.press("Control+k")
    page.get_by_role("combobox", name="Command search").fill("Studies")
    page.get_by_role("option", name="Open Studies").click()
    expect(page).to_have_url(f"{ui_base_url}/studies")


# ---------------------------------------------------------------------------
# Theme switching
# ---------------------------------------------------------------------------


def test_theme_switching_persists_across_navigation(page: Page, ui_base_url: str) -> None:
    page.goto(f"{ui_base_url}/dashboard")
    page.select_option("[data-theme-select]", "dark")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.get_by_role("navigation", name="Primary navigation").get_by_role(
        "link", name="Captures"
    ).click()
    expect(page).to_have_url(f"{ui_base_url}/captures")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
