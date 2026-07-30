"""Phase 14 condition ID registry tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from lumora_probe.analysis.contracts import (
    ConditionDefinition,
    ConditionId,
    ConditionIdRegistry,
)
from lumora_probe.analysis.service import ConditionDetector, default_condition_registry
from lumora_probe.shared.errors import DomainInvariantError
from lumora_probe.shared.events import EventEnvelope, EventOrigin

pytestmark = pytest.mark.unit


def _definition(condition_id: str, name: str = "No presentation context") -> ConditionDefinition:
    return ConditionDefinition(
        condition_id=condition_id,
        name=name,
        description="No acceptable presentation context was negotiated.",
        remediation="Review the offered SOP class and transfer syntax contexts.",
    )


def test_condition_id_validates_and_formats_parts() -> None:
    condition_id = ConditionId.from_parts("NEG", 4)

    assert condition_id.value == "LP-NEG-004"
    assert str(condition_id) == "LP-NEG-004"
    assert ConditionId("LP-NEG-004") == condition_id


@pytest.mark.parametrize(
    "value",
    ["LP-NEG-4", "LP-neg-004", "LP-NEGO-004", "NEG-004", "LP-NEG-000", "LP-NEG-1000"],
)
def test_condition_id_rejects_invalid_values(value: str) -> None:
    with pytest.raises(DomainInvariantError):
        ConditionId(value)


def test_condition_id_registry_rejects_reuse_and_orders_entries() -> None:
    registry = ConditionIdRegistry(
        (
            _definition("LP-TRN-002", "Transfer syntax mismatch"),
            _definition("LP-NEG-004"),
        )
    )

    assert registry.ids() == (ConditionId("LP-NEG-004"), ConditionId("LP-TRN-002"))
    assert registry.require("LP-NEG-004").name == "No presentation context"
    assert registry.get("LP-UNK-001") is None
    assert len(registry) == 2

    with pytest.raises(DomainInvariantError, match="already registered"):
        registry.register(_definition("LP-NEG-004", "Renamed condition"))


def test_condition_definition_normalizes_text_and_registry_contains_only_typed_ids() -> None:
    definition = ConditionDefinition(
        condition_id="LP-NEG-004",
        name="  No presentation context  ",
        description="  observed fact  ",
        remediation="  inspect negotiation  ",
    )
    registry = ConditionIdRegistry([definition])

    assert definition.name == "No presentation context"
    assert definition.description == "observed fact"
    assert definition.remediation == "inspect negotiation"
    assert ConditionId("LP-NEG-004") in registry
    assert "LP-NEG-004" not in registry


UUIDS = (
    "018f0d4e-7b6a-7000-8000-000000000011",
    "018f0d4e-7b6a-7000-8000-000000000012",
    "018f0d4e-7b6a-7000-8000-000000000013",
)


def _event(
    name: str,
    payload: dict[str, Any],
    *,
    event_id: str = UUIDS[0],
    origin: EventOrigin = EventOrigin.OBSERVED,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=event_id,
        event_name=name,
        event_version=1,
        occurred_at=datetime(2026, 7, 30, tzinfo=UTC),
        correlation_id=UUIDS[1],
        aggregate_type="Association",
        aggregate_id="association-1",
        producer="test",
        payload=payload,
        origin=origin,
        monotonic_ns=1,
        sequence=7,
    )


def test_condition_detector_maps_observed_rejection_without_acceptable_context() -> None:
    condition = ConditionDetector().detect(
        [_event("AssociationRejected", {"accepted_contexts": (), "reason": "no context"})]
    )[0]

    assert condition.code == "LP-NEG-004"
    assert condition.event_name == "WarningRaised"
    assert condition.source_sequence == 7
    assert condition.as_payload(name="No acceptable presentation context")["code"] == "LP-NEG-004"


def test_condition_detector_keeps_explicit_codes_and_is_idempotent() -> None:
    event = _event("WarningRaised", {"code": "LP-NEG-001", "reason": "peer rejected"})
    conditions = ConditionDetector().detect([event, event])

    assert len(conditions) == 1
    assert conditions[0].code == "LP-NEG-001"
    assert conditions[0].message == "peer rejected"


def test_condition_detector_excludes_client_asserted_and_unknown_codes() -> None:
    detector = ConditionDetector()

    assert (
        detector.detect(
            [
                _event(
                    "AssociationRejected",
                    {"accepted_contexts": ()},
                    origin=EventOrigin.CLIENT_ASSERTED,
                )
            ]
        )
        == ()
    )
    assert detector.detect([_event("WarningRaised", {"code": "LP-UNK-001"})]) == ()


def test_condition_catalogue_artifact_matches_registry() -> None:
    artifact = json.loads(Path("docs/generated/condition-catalog-v1.json").read_text())

    assert artifact == default_condition_registry().catalog()
