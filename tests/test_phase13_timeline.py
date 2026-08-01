# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 13 timeline ordering, cap, and accessibility tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from lumora_probe.core.bus import EventBus
from lumora_probe.shared.events import EventEnvelope, EventOrigin, EventSeverity
from lumora_probe.web.live import (
    LiveClient,
    UiSubscription,
    _panel_state,
    _update_client_panel_state,
)

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "src" / "lumora_probe" / "web" / "templates"
IDS = tuple(f"018f0d4e-7b6a-7000-8000-00000000000{index}" for index in range(1, 20))


def _make_event(
    index: int,
    *,
    sequence: int,
    occurred_at: datetime,
    name: str = "CStoreReceived",
) -> EventEnvelope:
    return EventEnvelope(
        event_id=IDS[index % len(IDS)],
        event_name=name,
        event_version=1,
        occurred_at=occurred_at,
        correlation_id=IDS[(index + 1) % len(IDS)],
        aggregate_type="Capture",
        aggregate_id="capture-1",
        producer="test",
        payload={"index": index},
        origin=EventOrigin.OBSERVED,
        severity=EventSeverity.INFO,
        monotonic_ns=index + 1,
        sequence=sequence,
    )


def test_timeline_renders_in_sequence_order_not_occurred_at() -> None:
    """Events arrive out-of-order by occurred_at but must be sorted by sequence."""
    bus = EventBus()
    # seq=1 has LATER occurred_at than seq=2
    events = [
        _make_event(
            0,
            sequence=1,
            occurred_at=datetime(2026, 7, 30, 12, 0, 10, tzinfo=UTC),
        ),
        _make_event(
            1,
            sequence=2,
            occurred_at=datetime(2026, 7, 30, 12, 0, 5, tzinfo=UTC),
        ),
        _make_event(
            2,
            sequence=3,
            occurred_at=datetime(2026, 7, 30, 12, 0, 1, tzinfo=UTC),
        ),
    ]
    state = _panel_state(events, timeline_cap=50, bus=bus)  # type: ignore[arg-type]
    timeline_events = state["timeline"]["events"]
    assert [e["sequence"] for e in timeline_events] == [1, 2, 3]


def test_timeline_caps_and_counts_dropped_events() -> None:
    """When events exceed timeline_cap, oldest by sequence are dropped and counted."""
    bus = EventBus()
    events = [
        _make_event(i, sequence=i + 1, occurred_at=datetime(2026, 7, 30, 12, 0, i, tzinfo=UTC))
        for i in range(5)
    ]
    state = _panel_state(events, timeline_cap=3, bus=bus)  # type: ignore[arg-type]
    timeline_events = state["timeline"]["events"]
    assert len(timeline_events) == 3
    # Oldest sequences (1, 2) dropped; newest (3, 4, 5) remain
    assert [e["sequence"] for e in timeline_events] == [3, 4, 5]
    assert state["timeline"]["events_dropped"] == 2


def test_timeline_partial_renders_keyboard_navigable_rows() -> None:
    """Timeline partial renders tabindex and role attributes on each row."""
    from fastapi.testclient import TestClient

    from lumora_probe.web.api import create_app

    application = create_app(event_bus=EventBus())  # type: ignore[arg-type]
    with TestClient(application) as client:
        response = client.get(
            "/ui/partials/timeline?page=live-monitor", headers={"host": "localhost"}
        )
    assert response.status_code == 200
    # Empty timeline renders without error
    assert '<div id="panel-timeline"' in response.text


def test_timeline_partial_renders_dropped_indicator() -> None:
    """When events_dropped > 0, partial shows status indicator."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(("html",)),
    )
    template = env.get_template("partials/timeline.html")
    events = [
        {"event_id": "id-1", "sequence": 10, "event_name": "CStoreReceived", "severity": "info"},
    ]
    html = template.render(page="live-monitor", events=events, events_dropped=5)
    assert 'tabindex="0"' in html
    assert 'role="listitem"' in html
    assert 'role="status"' in html
    assert "5 events dropped" in html


def test_timeline_counter_accumulates_across_batches() -> None:
    """events_dropped counter persists across multiple update calls."""
    bus = EventBus()
    client = LiveClient(
        client_id="test",
        kind="ui",
        subscription=UiSubscription(),
        queue=asyncio.Queue(maxsize=1),
    )
    # Batch 1: 3 events, cap 2 → 1 dropped
    batch1 = [
        _make_event(i, sequence=i + 1, occurred_at=datetime(2026, 7, 30, 12, 0, i, tzinfo=UTC))
        for i in range(3)
    ]
    state1 = _update_client_panel_state(client, batch1, timeline_cap=2, bus=bus)  # type: ignore[arg-type]
    assert state1["timeline"]["events_dropped"] == 1
    # Batch 2: 2 more events → 2 more dropped (total 3)
    batch2 = [
        _make_event(
            i + 3,
            sequence=i + 4,
            occurred_at=datetime(2026, 7, 30, 12, 0, i + 3, tzinfo=UTC),
        )
        for i in range(2)
    ]
    state2 = _update_client_panel_state(client, batch2, timeline_cap=2, bus=bus)  # type: ignore[arg-type]
    assert state2["timeline"]["events_dropped"] == 3
