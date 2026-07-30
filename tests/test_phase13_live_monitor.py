"""Phase 13 live monitor associations and drop counter tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from lumora_probe.core.bus import EventBus
from lumora_probe.shared.events import EventEnvelope, EventOrigin, EventSeverity
from lumora_probe.web.live import (
    CoalescingGovernor,
    LiveSettings,
)
from lumora_probe.web.resources import InMemoryResourceStore

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


async def test_live_monitor_lists_active_associations() -> None:
    """Governor surfaces active associations from the store into UI client status state."""
    bus = EventBus()
    governor = CoalescingGovernor(bus=bus)  # type: ignore[arg-type]  # type: ignore[arg-type]
    store = InMemoryResourceStore(
        {
            "associations": {
                "assoc-1": {"association_id": "assoc-1", "remote_ae": "STORE_A"},
                "assoc-2": {"association_id": "assoc-2", "remote_ae": "STORE_B"},
            }
        }
    )
    client = governor.register_ui(page="workspace", panels=("status",), topics=("*",))

    await governor.refresh_associations(store)

    assert "assoc:assoc-1" in client.status_state
    assert "assoc:assoc-2" in client.status_state
    assert client.status_state["assoc:assoc-1"]["event_name"] == "Association"
    assert client.status_state["assoc:assoc-1"]["severity"] == "info"
    assert client.status_state["assoc:assoc-1"]["sequence"] is None
    assert client.status_state["assoc:assoc-2"]["aggregate_id"] == "assoc-2"


async def test_live_monitor_drop_counter_after_governor_drops() -> None:
    """Timeline cap overflow increments events_dropped counter."""
    bus = EventBus()
    governor = CoalescingGovernor(bus=bus, settings=LiveSettings(timeline_cap=2))  # type: ignore[arg-type]
    client = governor.register_ui(page="workspace", panels=("timeline",), topics=("*",))

    events = [
        _make_event(
            i,
            sequence=i + 1,
            occurred_at=datetime(2026, 7, 30, 12, 0, i, tzinfo=UTC),
        )
        for i in range(5)
    ]
    for event in events:
        await governor.publish(event)
    await governor.flush_now()

    assert client.counter_state["events_dropped"] == 3


def test_counters_partial_renders_dropped_indicator() -> None:
    """Counters template shows dropped-events paragraph when events_dropped > 0."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(("html", "xml")),
    )
    template = env.get_template("partials/counters.html")
    html = template.render(
        page="workspace",
        panel="counters",
        counters={"events": 10},
        events_dropped=3,
    )
    assert "3 events dropped" in html
    assert "counters-dropped" in html


async def test_counters_partial_omits_dropped_indicator_when_zero() -> None:
    """Counters template hides dropped paragraph when events_dropped is zero."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(("html", "xml")),
    )
    template = env.get_template("partials/counters.html")
    html = template.render(
        page="workspace",
        panel="counters",
        counters={"events": 10},
        events_dropped=0,
    )
    assert "events dropped" not in html


async def test_refresh_associations_clears_previous_rows() -> None:
    """Re-refreshing replaces old association rows with the new set."""
    bus = EventBus()
    governor = CoalescingGovernor(bus=bus)  # type: ignore[arg-type]
    store = InMemoryResourceStore(
        {
            "associations": {
                "assoc-1": {"association_id": "assoc-1"},
                "assoc-2": {"association_id": "assoc-2"},
            }
        }
    )
    client = governor.register_ui(page="workspace", panels=("status",), topics=("*",))

    await governor.refresh_associations(store)
    assert "assoc:assoc-1" in client.status_state
    assert "assoc:assoc-2" in client.status_state

    # Replace with a single association
    await store.delete("associations", "assoc-2")
    await governor.refresh_associations(store)

    assert "assoc:assoc-1" in client.status_state
    assert "assoc:assoc-2" not in client.status_state


async def test_refresh_associations_noop_when_store_none() -> None:
    """Passing None for the store is a no-op."""
    bus = EventBus()
    governor = CoalescingGovernor(bus=bus)  # type: ignore[arg-type]
    client = governor.register_ui(page="workspace", panels=("status",), topics=("*",))

    await governor.refresh_associations(None)

    assert not any(key.startswith("assoc:") for key in client.status_state)


async def test_refresh_associations_skips_json_clients() -> None:
    """JSON stream clients are not affected by association refresh."""
    bus = EventBus()
    governor = CoalescingGovernor(bus=bus)  # type: ignore[arg-type]
    store = InMemoryResourceStore({"associations": {"assoc-1": {"association_id": "assoc-1"}}})
    json_client = governor.register_stream(topics=("*",))

    await governor.refresh_associations(store)

    assert not any(key.startswith("assoc:") for key in json_client.status_state)
