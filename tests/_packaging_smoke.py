"""Standalone packaging smoke test — run without Node on PATH.

Verifies the application can import, render routes, and serve without
any Node/npm runtime dependency.  Invoked by test_phase25_packaging.py
via subprocess.
"""

from __future__ import annotations

import asyncio

import httpx


def main() -> None:
    from lumora_probe.web.api import create_app

    app = create_app()

    async def _check() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            resp = await client.get("/dashboard")
            assert resp.status_code == 200
            assert "Lumora Probe" in resp.text
            print("OK")

    asyncio.run(_check())


if __name__ == "__main__":
    main()
