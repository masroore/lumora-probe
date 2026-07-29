"""Phase 07 settings provenance event tests."""

from __future__ import annotations

from datetime import UTC, datetime

from lumora_probe.settings.runtime import RuntimeSettingsStore, _redact_setting_value
from tests.doubles.clock import ControllableClock
from tests.doubles.ids import SeededIdGenerator


class FakePublisher:
    def __init__(self) -> None:
        self.events = []

    def publish_from_thread(self, event):
        self.events.append(event)


def test_runtime_setting_update_publishes_redacted_configuration_event(tmp_path) -> None:
    publisher = FakePublisher()
    store = RuntimeSettingsStore(
        tmp_path / "settings.toml",
        event_publisher=publisher,
        clock=ControllableClock(datetime(2026, 7, 29, tzinfo=UTC), monotonic_ns=10),
        id_generator=SeededIdGenerator(
            [
                "018f0d4e-7b6a-7000-8000-000000000001",
                "018f0d4e-7b6a-7000-8000-000000000002",
            ]
        ),
    )

    store.update("theme", "dark")

    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.event_name == "ConfigurationChanged"
    assert event.payload == {
        "setting": "theme",
        "old_value": "system",
        "new_value": "dark",
        "old_source": "default",
        "new_source": "runtime",
    }
    assert _redact_setting_value("api_token", "secret") == "[REDACTED]"
