"""Phase 13 browser e2e: window/level interaction requires no server round trip.

Setup: uv run playwright install chromium
Run: LUMORA_E2E=1 uv run pytest -m e2e tests/test_phase13_viewer_e2e.py
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_window_level_drag_makes_no_frame_requests() -> None:
    """W/L drag must not trigger any frame or metadata endpoint requests.

    This is the Phase 13 exit-criterion assertion: client-side W/L stays local
    with zero round trips. ADR-0030 owns ratified budgets; this is a smoke bound.
    """
    import asyncio
    import socket

    import uvicorn
    from playwright.async_api import async_playwright

    from lumora_probe.web.api import create_app

    app = create_app()

    # Find a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    await asyncio.sleep(0.5)  # allow server to start

    frame_requests: list[str] = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Count requests to frame/metadata endpoints
            def on_request(request):
                url = request.url
                if "/frames/" in url or "/metadata/" in url:
                    frame_requests.append(url)

            page.on("request", on_request)

            await page.goto(f"http://127.0.0.1:{port}/")
            await page.wait_for_load_state("networkidle")

            # Perform a synthetic W/L drag on the viewer canvas
            canvas = page.locator("canvas").first
            if await canvas.count() > 0:
                box = await canvas.bounding_box()
                if box:
                    start_x = box["x"] + box["width"] / 2
                    start_y = box["y"] + box["height"] / 2
                    await page.mouse.move(start_x, start_y)
                    await page.mouse.down()
                    # 30 drag frames — smoke bound, not a precision benchmark
                    for i in range(30):
                        await page.mouse.move(start_x + i * 2, start_y + i)
                    await page.mouse.up()

            await browser.close()
    finally:
        server.should_exit = True
        await server_task

    # Zero requests to frame/metadata endpoints during the drag
    assert frame_requests == [], (
        f"W/L drag triggered {len(frame_requests)} frame/metadata requests: {frame_requests}"
    )
