# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 07 event contract, registry, and catalog tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from lumora_probe.shared.events import (
    DEFAULT_EVENT_REGISTRY,
    EventCategory,
    EventEnvelope,
    EventOrigin,
    EventPayloadRegistry,
    UnknownEventPayload,
)

UUIDS = (
    "018f0d4e-7b6a-7000-8000-000000000001",
    "018f0d4e-7b6a-7000-8000-000000000002",
    "018f0d4e-7b6a-7000-8000-000000000003",
    "018f0d4e-7b6a-7000-8000-000000000004",
    "018f0d4e-7b6a-7000-8000-000000000005",
)


def make_event(
    name: str = "CStoreReceived",
    *,
    aggregate_id: str = "capture-1",
    monotonic_ns: int = 1,
    payload: dict[str, Any] | None = None,
    origin: EventOrigin = EventOrigin.OBSERVED,
    producer: str = "test",
    occurred_at: datetime | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=UUIDS[0],
        event_name=name,
        event_version=1,
        occurred_at=occurred_at or datetime(2026, 7, 29, 12, 0, tzinfo=UTC),
        correlation_id=UUIDS[1],
        aggregate_type="Capture",
        aggregate_id=aggregate_id,
        producer=producer,
        payload=payload or {"sop_count": 1},
        origin=origin,
        monotonic_ns=monotonic_ns,
    )


def test_envelope_requires_origin_and_preserves_future_fields() -> None:
    with pytest.raises(ValidationError):
        EventEnvelope(
            event_id=UUIDS[0],
            event_name="CStoreReceived",
            event_version=1,
            occurred_at=datetime.now(UTC),
            correlation_id=UUIDS[1],
            aggregate_type="Capture",
            aggregate_id="capture-1",
            producer="test",
            payload={},
            monotonic_ns=1,
        )

    event = EventEnvelope.model_validate(
        {
            **make_event().model_dump(),
            "future_envelope_field": {"preserve": True},
            "payload": {"known": 1, "future_payload_field": "kept"},
        }
    )
    dumped = event.model_dump()
    assert dumped["future_envelope_field"] == {"preserve": True}
    assert dumped["payload"]["future_payload_field"] == "kept"
    assert event.model_copy(update={"sequence": 1}).model_dump()["sequence"] == 1


def test_event_name_and_uuid_invariants_are_enforced() -> None:
    with pytest.raises(ValidationError):
        make_event(name="start_association")
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate({**make_event().model_dump(), "event_id": "not-a-uuidv7"})
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(
            {**make_event().model_dump(), "occurred_at": "2026-07-29T00:00:00"}
        )


def test_registry_validates_known_payload_and_preserves_unknown_pair() -> None:
    class StorePayload(BaseModel):
        model_config = ConfigDict(extra="forbid")

        sop_count: int

    registry = EventPayloadRegistry()
    registry.register("CStoreReceived", 1, EventCategory.DIMSE, StorePayload)
    assert registry.validate(make_event(payload={"sop_count": 3})).sop_count == 3
    unknown = registry.parse_payload("FutureEvent", 9, {"new_field": "kept"})
    assert isinstance(unknown, UnknownEventPayload)
    assert unknown.model_dump()["new_field"] == "kept"
    with pytest.raises(ValidationError):
        registry.validate(make_event(payload={"unexpected": True}))


def test_default_catalog_covers_all_ten_categories_and_is_generated() -> None:
    catalog = DEFAULT_EVENT_REGISTRY.catalog()
    categories = {item["category"] for item in catalog["events"]}
    assert categories == {category.value for category in EventCategory}
    assert catalog["catalog_version"] == 1
    assert catalog["envelope"]["unknown_fields"] == "preserved"
    artifact = Path("docs/generated/event-catalog-v1.json")
    assert json.loads(artifact.read_text(encoding="utf-8")) == catalog
