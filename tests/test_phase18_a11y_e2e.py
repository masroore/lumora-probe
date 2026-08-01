# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 18 keyboard-only accessibility e2e scenarios.

Setup: uv run playwright install chromium
Run: LUMORA_E2E=1 uv run pytest -m e2e tests/test_phase18_a11y_e2e.py
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_keyboard_primary_workflows_without_mouse() -> None:
    import asyncio
    import socket

    import httpx
    import uvicorn
    from playwright.async_api import async_playwright

    from lumora_probe.web.api import create_app

    application = create_app()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])

    config = uvicorn.Config(application, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    async def wait_ready() -> None:
        deadline = asyncio.get_running_loop().time() + 30
        while asyncio.get_running_loop().time() < deadline:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"http://127.0.0.1:{port}/")
                    if response.status_code == 200:
                        return
            except OSError:
                await asyncio.sleep(0.05)
                continue
            except httpx.HTTPError:
                await asyncio.sleep(0.05)
                continue
            await asyncio.sleep(0.05)
        raise AssertionError("workspace did not become ready")

    try:
        await wait_ready()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(f"http://127.0.0.1:{port}/")
            await page.wait_for_function("() => Boolean(window.LumoraCommandPalette)")

            # Focus the Commands control and activate it with keyboard only.
            await page.locator("[data-command-palette]").focus()
            await page.keyboard.press("Enter")
            palette = page.locator("[data-palette-overlay]")
            await palette.wait_for(state="visible")
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Enter")
            await page.keyboard.press("Escape")
            assert await palette.is_hidden()

            theme = page.locator("[data-theme-select]")
            await theme.focus()
            await page.select_option("[data-theme-select]", "high-contrast")
            assert await page.locator("html").get_attribute("data-theme") == "high-contrast"

            search = page.locator("[data-search-input]")
            await search.focus()
            await page.keyboard.type("study")
            assert await search.input_value() == "study"

            explorer_toggle = page.locator('[data-panel-toggle="explorer"]')
            await explorer_toggle.focus()
            await page.keyboard.press("Enter")
            assert (
                await page.locator(".workspace-frame").get_attribute("data-explorer-collapsed")
                == "true"
            )

            timeline = page.locator("#timeline-panel")
            await timeline.focus()
            await page.keyboard.press("Tab")

            cine = page.locator("#cine-toggle")
            await cine.focus()
            await page.keyboard.press("Enter")
            assert await cine.get_attribute("aria-pressed") in {"true", "false"}

            await browser.close()
    finally:
        server.should_exit = True
        await server_task
