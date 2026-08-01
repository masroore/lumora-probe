# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 18 concurrent local client matrix for /ws/ui and /api/v1/events/stream."""

from __future__ import annotations

import time
from contextlib import ExitStack
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from lumora_probe.core.bus import EventBus
from lumora_probe.shared.events import EventEnvelope, EventOrigin
from lumora_probe.web.api import create_app

IDS = tuple(f"018f0d4e-7b6a-7000-8000-00000000{index:04d}" for index in range(1, 32))


def make_event(index: int) -> EventEnvelope:
    return EventEnvelope(
        event_id=IDS[index % len(IDS)],
        event_name="CStoreReceived",
        event_version=1,
        occurred_at=datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
        correlation_id=IDS[(index + 1) % len(IDS)],
        aggregate_type="Capture",
        aggregate_id="capture-concurrent",
        producer="phase18",
        payload={"index": index},
        origin=EventOrigin.OBSERVED,
        monotonic_ns=index + 1,
        sequence=index + 1,
    )


@pytest.mark.component
def test_concurrent_ui_and_event_stream_clients() -> None:
    application = create_app(event_bus=EventBus())
    matrix: list[dict[str, object]] = []

    with TestClient(application) as client:
        for ui_count in (1, 4, 8):
            started = time.monotonic()
            with ExitStack() as stack:
                ui_sockets = [
                    stack.enter_context(
                        client.websocket_connect("/ws/ui", headers={"host": "localhost"})
                    )
                    for _ in range(ui_count)
                ]
                stream_ws = stack.enter_context(
                    client.websocket_connect("/api/v1/events/stream", headers={"host": "localhost"})
                )
                for ws in ui_sockets:
                    assert ws.receive_json()["mounted"] is False
                    ws.send_json(
                        {
                            "type": "mount",
                            "page": "live-monitor",
                            "panels": ["timeline"],
                            "topics": ["Capture"],
                        }
                    )
                    assert ws.receive_json()["type"] == "mounted"
                assert stream_ws.receive_json()["type"] == "ready"
                stream_ws.send_json({"type": "subscribe", "topics": ["Capture"]})
                assert stream_ws.receive_json()["type"] == "subscribed"

                for index in range(20):
                    application.state.event_bus.publish_from_thread(make_event(index)).result(
                        timeout=2
                    )

                stream_message = stream_ws.receive_json()
                assert stream_message["type"] == "events"
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
                    "stream_clients": 1,
                    "elapsed_seconds": time.monotonic() - started,
                    "completed": True,
                }
            )

    assert matrix[-1]["ui_clients"] == 8
    assert all(row["completed"] for row in matrix)
    print({"dimension": "concurrent_clients", "matrix": matrix})
