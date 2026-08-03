# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 25 UI performance measurement for large-table, viewer, and live-update scenarios.

Measurements are evidence only — timing thresholds reference ADR-0030 and ADR-0037
where ratified, and are reported as measured where unfitted.

Run: uv run pytest -m component tests/test_phase25_performance.py
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from lumora_probe.core.bus import EventBus
from lumora_probe.shared.events import EventEnvelope, EventOrigin
from lumora_probe.web.api import create_app

_HOST = {"host": "localhost"}

IDS = tuple(f"025f0d4e-7b6a-7000-8000-00000000{index:04d}" for index in range(1, 1001))


def _make_event(index: int) -> EventEnvelope:
    return EventEnvelope(
        event_id=IDS[index % len(IDS)],
        event_name="CStoreReceived",
        event_version=1,
        occurred_at=datetime(2026, 8, 3, 12, 0, tzinfo=UTC),
        correlation_id=IDS[(index + 1) % len(IDS)],
        aggregate_type="Capture",
        aggregate_id="capture-perf",
        producer="phase25",
        payload={"index": index},
        origin=EventOrigin.OBSERVED,
        monotonic_ns=index + 1,
        sequence=index + 1,
    )


# ---------------------------------------------------------------------------
# Dashboard render time
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_dashboard_render_under_budget() -> None:
    """Dashboard full-page render within 250 ms (ADR-0037 reference)."""
    application = create_app(event_bus=EventBus())

    with TestClient(application) as client:
        times: list[float] = []
        for _ in range(5):
            start = time.perf_counter()
            resp = client.get("/dashboard", headers=_HOST)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = sorted(times)[int(len(times) * 0.95)]
        assert p95 < 250, f"dashboard p95 {p95:.1f} ms exceeds 250 ms budget"
        print(f"dashboard: median={sorted(times)[len(times) // 2]:.1f}ms p95={p95:.1f}ms")


# ---------------------------------------------------------------------------
# HTMX fragment render time
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_htmx_fragment_render_under_budget() -> None:
    """HTMX fragment swap within 100 ms (ADR-0019 governor budget)."""
    application = create_app(event_bus=EventBus())

    with TestClient(application) as client:
        times: list[float] = []
        for _ in range(5):
            start = time.perf_counter()
            resp = client.get("/dashboard", headers={**_HOST, "HX-Request": "true"})
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = sorted(times)[int(len(times) * 0.95)]
        assert p95 < 100, f"HTMX fragment p95 {p95:.1f} ms exceeds 100 ms"
        print(f"htmx_fragment: median={sorted(times)[len(times) // 2]:.1f}ms p95={p95:.1f}ms")


# ---------------------------------------------------------------------------
# Event bus throughput
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_event_bus_throughput() -> None:
    """Publish 500 events through the bus and measure throughput."""
    bus = EventBus()
    application = create_app(event_bus=bus)

    with TestClient(application) as client:
        with client.websocket_connect("/ws/ui", headers=_HOST) as ws:
            ws.receive_json()
            ws.send_json(
                {
                    "type": "mount",
                    "page": "live-monitor",
                    "panels": ["timeline", "counters"],
                    "topics": ["Capture"],
                }
            )
            assert ws.receive_json()["type"] == "mounted"

            start = time.perf_counter()
            for idx in range(500):
                bus.publish_from_thread(_make_event(idx)).result(timeout=2)
            publish_elapsed = time.perf_counter() - start

            msg = ws.receive_json()
            elapsed = time.perf_counter() - start
            ws.close()

        assert msg["type"] == "fragments"
        throughput = 500 / publish_elapsed if publish_elapsed > 0 else float("inf")
        print(
            f"bus_throughput: 500 events in {publish_elapsed:.3f}s "
            f"({throughput:.0f} events/s), total={elapsed:.3f}s"
        )
        assert "source_sequences" in msg


# ---------------------------------------------------------------------------
# Live update latency (WS round-trip)
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_live_update_round_trip_latency() -> None:
    """Measure event publish to UI fragment receive latency."""
    bus = EventBus()
    application = create_app(event_bus=bus)

    with TestClient(application) as client, client.websocket_connect("/ws/ui", headers=_HOST) as ws:
        ws.receive_json()
        ws.send_json(
            {
                "type": "mount",
                "page": "live-monitor",
                "panels": ["counters"],
                "topics": ["Capture"],
            }
        )
        assert ws.receive_json()["type"] == "mounted"

        latencies: list[float] = []
        for idx in range(10):
            start = time.perf_counter()
            bus.publish_from_thread(_make_event(idx)).result(timeout=2)
            msg = ws.receive_json()
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert msg["type"] == "fragments"

        median = sorted(latencies)[len(latencies) // 2]
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        ws.close()
        print(f"live_update: median={median:.1f}ms p95={p95:.1f}ms")
        assert p95 < 5000, f"live update p95 {p95:.1f}ms indicates regression"


# ---------------------------------------------------------------------------
# Captures list page
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_captures_list_render_performance() -> None:
    """Captures list renders within 500 ms."""
    application = create_app(event_bus=EventBus())

    with TestClient(application) as client:
        times: list[float] = []
        for _ in range(3):
            start = time.perf_counter()
            resp = client.get("/captures", headers=_HOST)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)
            assert resp.status_code == 200

        p95 = sorted(times)[int(len(times) * 0.95)]
        assert p95 < 500, f"captures list p95 {p95:.1f} ms exceeds 500 ms"
        print(f"captures_list: p95={p95:.1f}ms")


# ---------------------------------------------------------------------------
# Static asset sizes
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_static_asset_sizes_within_budgets() -> None:
    """Committed CSS and JS assets within reasonable size budgets."""
    from lumora_probe.web.workspace_routes import STATIC_ROOT

    css_path = STATIC_ROOT / "css" / "app.css"
    assert css_path.exists(), "app.css not found"
    css_size_kb = css_path.stat().st_size / 1024
    assert css_size_kb < 500, f"app.css is {css_size_kb:.0f} KB, exceeds 500 KB"
    print(f"app.css: {css_size_kb:.1f} KB")

    for js_file in STATIC_ROOT.glob("js/*.js"):
        size_kb = js_file.stat().st_size / 1024
        # Cornerstone renderer is intentionally large (compiled ESM bundle)
        budget = 1500 if js_file.name == "cornerstone-renderer.js" else 250
        assert size_kb < budget, f"{js_file.name} is {size_kb:.0f} KB, exceeds {budget} KB budget"
        print(f"{js_file.name}: {size_kb:.1f} KB")
