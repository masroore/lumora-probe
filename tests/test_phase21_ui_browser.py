# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 21 browser acceptance for navigation, tabs, history, focus, and commands."""

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


def test_navigation_history_focus_and_command_palette(page: Page, ui_base_url: str) -> None:
    external: list[str] = []
    page.on(
        "request",
        lambda request: (
            external.append(request.url) if not request.url.startswith(ui_base_url) else None
        ),
    )
    page.goto(f"{ui_base_url}/dashboard")
    page.get_by_role("navigation", name="Primary navigation").get_by_role(
        "link", name="Captures", exact=True
    ).click()
    expect(page).to_have_url(f"{ui_base_url}/captures")
    expect(page.locator("#workspace-view")).to_have_attribute("data-route-name", "captures")
    assert page.evaluate("document.activeElement.id") == "workspace-view"

    page.go_back()
    expect(page).to_have_url(f"{ui_base_url}/dashboard")
    page.keyboard.press("Control+k")
    page.get_by_role("combobox", name="Command search").fill("Studies")
    page.get_by_role("option", name="Open Studies").click()
    expect(page).to_have_url(f"{ui_base_url}/studies")
    assert external == []


def test_context_tabs_support_keyboard_and_url_history(page: Page, ui_base_url: str) -> None:
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
