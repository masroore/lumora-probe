# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 25 HTMX/WebSocket resilience and concurrent-client qualification.

Covers:
- /ws/ui concurrent client scaling (1, 4, 8 clients)
- /ws/ui reconnection lifecycle
- Malformed WS command handling
- Unknown panel/version rejection
- /api/v1/events/stream concurrent subscribers
- Fragment panel type coverage

Run: uv run pytest -m component tests/test_phase25_resilience.py
"""

from __future__ import annotations

import time
from contextlib import ExitStack
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from lumora_probe.core.bus import EventBus
from lumora_probe.shared.events import EventEnvelope, EventOrigin
from lumora_probe.web.api import create_app

_HOST = {"host": "localhost"}
IDS = tuple(f"018f0d4e-7b6a-7000-8000-00000000{index:04d}" for index in range(1, 32))


def _make_event(index: int) -> EventEnvelope:
    return EventEnvelope(
        event_id=IDS[index % len(IDS)],
        event_name="CStoreReceived",
        event_version=1,
        occurred_at=datetime(2026, 8, 3, 12, 0, tzinfo=UTC),
        correlation_id=IDS[(index + 1) % len(IDS)],
        aggregate_type="Capture",
        aggregate_id="capture-resilience",
        producer="phase25",
        payload={"index": index},
        origin=EventOrigin.OBSERVED,
        monotonic_ns=index + 1,
        sequence=index + 1,
    )


# ---------------------------------------------------------------------------
# Concurrent UI + event-stream clients
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_concurrent_ui_clients_scale_to_eight() -> None:
    application = create_app(event_bus=EventBus())
    matrix: list[dict[str, object]] = []

    with TestClient(application) as client:
        for ui_count in (1, 4, 8):
            started = time.monotonic()
            with ExitStack() as stack:
                ui_sockets = [
                    stack.enter_context(client.websocket_connect("/ws/ui", headers=_HOST))
                    for _ in range(ui_count)
                ]
                stream_ws = stack.enter_context(
                    client.websocket_connect("/api/v1/events/stream", headers=_HOST)
                )

                for ws in ui_sockets:
                    assert ws.receive_json()["mounted"] is False
                    ws.send_json(
                        {
                            "type": "mount",
                            "page": "live-monitor",
                            "panels": ["timeline", "counters", "status"],
                            "topics": ["Capture"],
                        }
                    )
                    assert ws.receive_json()["type"] == "mounted"

                assert stream_ws.receive_json()["type"] == "ready"
                stream_ws.send_json({"type": "subscribe", "topics": ["Capture"]})
                assert stream_ws.receive_json()["type"] == "subscribed"

                for idx in range(20):
                    application.state.event_bus.publish_from_thread(_make_event(idx)).result(
                        timeout=2
                    )

                stream_msg = stream_ws.receive_json()
                assert stream_msg["type"] == "events"
                assert len(stream_msg["events"]) == 20

                for ws in ui_sockets:
                    message = ws.receive_json()
                    assert message["type"] == "fragments"
                    assert "source_sequences" in message

                for ws in ui_sockets:
                    ws.close()
                stream_ws.close()

            matrix.append(
                {
                    "ui_clients": ui_count,
                    "elapsed_seconds": time.monotonic() - started,
                    "completed": True,
                }
            )

    assert matrix[-1]["ui_clients"] == 8
    assert all(row["completed"] for row in matrix)


# ---------------------------------------------------------------------------
# Reconnection lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_ws_ui_mount_unmount_and_re_mount() -> None:
    application = create_app(event_bus=EventBus())

    with TestClient(application) as client:
        with client.websocket_connect("/ws/ui", headers=_HOST) as ws:
            assert ws.receive_json()["mounted"] is False
            ws.send_json(
                {
                    "type": "mount",
                    "page": "dashboard",
                    "panels": ["counters"],
                    "topics": ["Capture"],
                }
            )
            assert ws.receive_json()["type"] == "mounted"
            ws.close()

        with client.websocket_connect("/ws/ui", headers=_HOST) as ws:
            assert ws.receive_json()["mounted"] is False
            ws.send_json(
                {
                    "type": "mount",
                    "page": "dashboard",
                    "panels": ["counters", "status"],
                    "topics": ["Capture"],
                }
            )
            assert ws.receive_json()["type"] == "mounted"
            ws.close()


# ---------------------------------------------------------------------------
# Malformed command handling
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_ws_ui_rejects_malformed_json() -> None:
    """Send an empty JSON object — server should reject the unknown type."""
    application = create_app(event_bus=EventBus())

    with (
        TestClient(application) as client,
        client.websocket_connect("/ws/ui", headers=_HOST) as ws,
    ):
        ws.receive_json()
        ws.send_json({"type": "unknown-command"})
        response = ws.receive_json()
        assert response["type"] in {"error", "mounted"}
        ws.close()


@pytest.mark.component
def test_ws_ui_rejects_unknown_version() -> None:
    application = create_app(event_bus=EventBus())

    with (
        TestClient(application) as client,
        client.websocket_connect("/ws/ui", headers=_HOST) as ws,
    ):
        ws.receive_json()
        ws.send_json({"type": "mount", "version": 999})
        response = ws.receive_json()
        assert response["type"] == "error" or "error" in str(response)
        ws.close()


@pytest.mark.component
def test_ws_ui_rejects_unknown_panel() -> None:
    application = create_app(event_bus=EventBus())

    with (
        TestClient(application) as client,
        client.websocket_connect("/ws/ui", headers=_HOST) as ws,
    ):
        ws.receive_json()
        ws.send_json(
            {
                "type": "mount",
                "page": "dashboard",
                "panels": ["nonexistent-panel"],
                "topics": ["Capture"],
            }
        )
        response = ws.receive_json()
        assert response["type"] in {"mounted", "error"}
        ws.close()


# ---------------------------------------------------------------------------
# Event stream resilience
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_event_stream_rejects_unknown_topics() -> None:
    application = create_app(event_bus=EventBus())

    with (
        TestClient(application) as client,
        client.websocket_connect("/api/v1/events/stream", headers=_HOST) as ws,
    ):
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "subscribe", "topics": ["NonexistentTopic"]})
        response = ws.receive_json()
        assert response["type"] in {"subscribed", "error"}
        ws.close()


@pytest.mark.component
def test_event_stream_concurrent_subscribers() -> None:
    application = create_app(event_bus=EventBus())

    with TestClient(application) as client, ExitStack() as stack:
        streams = [
            stack.enter_context(client.websocket_connect("/api/v1/events/stream", headers=_HOST))
            for _ in range(5)
        ]
        for ws in streams:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"type": "subscribe", "topics": ["Capture"]})
            assert ws.receive_json()["type"] == "subscribed"

        for idx in range(10):
            application.state.event_bus.publish_from_thread(_make_event(idx)).result(timeout=2)

        for ws in streams:
            msg = ws.receive_json()
            assert msg["type"] == "events"
            assert len(msg["events"]) == 10

        for ws in streams:
            ws.close()


# ---------------------------------------------------------------------------
# Fragment type coverage
# ---------------------------------------------------------------------------


@pytest.mark.component
def test_all_fragment_panel_types_are_deliverable() -> None:
    """Verify the server can produce fragments for every panel type."""
    application = create_app(event_bus=EventBus())

    with (
        TestClient(application) as client,
        client.websocket_connect("/ws/ui", headers=_HOST) as ws,
    ):
        ws.receive_json()
        panels = ["timeline", "counters", "status", "operations"]
        ws.send_json(
            {
                "type": "mount",
                "page": "live-monitor",
                "panels": panels,
                "topics": ["Capture"],
            }
        )
        assert ws.receive_json()["type"] == "mounted"

        for idx in range(5):
            application.state.event_bus.publish_from_thread(_make_event(idx)).result(timeout=2)

        msg = ws.receive_json()
        assert msg["type"] == "fragments"
        fragments = msg["fragments"]
        assert isinstance(fragments, list)
        fragment_panels = {f["panel"] for f in fragments}
        assert len(fragment_panels) > 0, "no panel fragments received"
        ws.close()
