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
    Finding,
    FindingConfidence,
)
from lumora_probe.analysis.service import (
    ConditionDetector,
    RuleContext,
    RuleEngine,
    default_condition_registry,
)
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


def test_finding_model_preserves_version_confidence_and_evidence_links() -> None:
    finding = Finding(
        rule_id="LP-RULE-NEG-001",
        rule_version="2026-07-30",
        confidence=FindingConfidence.CERTAIN,
        cited_sequences=[2, 7],
        explanation="The peer rejected negotiation after no acceptable context was offered.",
        next_steps=["Compare offered contexts", "Review peer configuration"],
    )

    assert finding.sequence_numbers == (2, 7)
    assert finding.as_dict() == {
        "rule_id": "LP-RULE-NEG-001",
        "rule_version": "2026-07-30",
        "rule_set_version": "bundled-v1",
        "confidence": "certain",
        "cited_sequences": [2, 7],
        "explanation": "The peer rejected negotiation after no acceptable context was offered.",
        "next_steps": ["Compare offered contexts", "Review peer configuration"],
    }


@pytest.mark.parametrize("confidence", ["73%", "high", 0.73])
def test_finding_model_rejects_numeric_or_unknown_confidence(confidence: object) -> None:
    with pytest.raises(DomainInvariantError):
        Finding(
            rule_id="LP-RULE-NEG-001",
            rule_version="1",
            confidence=confidence,  # type: ignore[arg-type]
            cited_sequences=(1,),
            explanation="Observed explanation",
            next_steps=("Inspect evidence",),
        )


def test_finding_model_requires_sorted_unique_evidence_and_next_steps() -> None:
    with pytest.raises(DomainInvariantError, match="unique and sorted"):
        Finding(
            rule_id="rule",
            rule_version="1",
            confidence="likely",
            cited_sequences=(3, 2, 3),
            explanation="Observed explanation",
            next_steps=("Inspect evidence",),
        )
    with pytest.raises(DomainInvariantError, match="next_steps"):
        Finding(
            rule_id="rule",
            rule_version="1",
            confidence="likely",
            cited_sequences=(2,),
            explanation="Observed explanation",
            next_steps=("",),
        )


def test_analysis_repository_writes_only_analysis_directory_and_round_trips(tmp_path: Path) -> None:
    from lumora_probe.analysis.repository import AnalysisRepository

    capture_path = tmp_path / "capture"
    capture_path.mkdir()
    events_path = capture_path / "events.jsonl"
    events_path.write_text('{"event_name":"AssociationRejected"}\n', encoding="utf-8")
    finding = Finding(
        rule_id="LP-RULE-NEG-001",
        rule_version="1",
        confidence="certain",
        cited_sequences=(7,),
        explanation="The observed negotiation was rejected.",
        rule_set_version="rules-v1",
        next_steps=("Inspect peer negotiation",),
    )
    repository = AnalysisRepository(capture_path)

    path = repository.write_findings((finding,), rule_set_version="rules-v1")

    assert path == capture_path / "analysis" / "findings.json"
    assert repository.read_findings() == (finding,)
    assert events_path.read_text(encoding="utf-8") == '{"event_name":"AssociationRejected"}\n'
    assert not (capture_path / "events.jsonl.tmp").exists()

    first_bytes = path.read_bytes()
    repository.delete_findings()
    assert not path.exists()
    repository.write_findings((finding,), rule_set_version="rules-v1")
    assert path.read_bytes() == first_bytes


class _Rule:
    rule_id = "LP-RULE-TEST-001"
    rule_version = "1"

    def evaluate(self, context: RuleContext) -> tuple[Finding, ...]:
        assert len(context.events) == 1
        assert context.conditions[0].code == "LP-NEG-004"
        return (
            Finding(
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                confidence="certain",
                cited_sequences=(7,),
                explanation="The observed association had no acceptable context.",
                next_steps=("Compare offered contexts",),
            ),
        )


def test_rule_engine_excludes_client_asserted_events_and_validates_citations() -> None:
    observed = _event("AssociationRejected", {"accepted_contexts": ()})
    client = _event(
        "ImageDisplayed",
        {"condition_code": "LP-NEG-004"},
        event_id=UUIDS[2],
        origin=EventOrigin.CLIENT_ASSERTED,
    )

    findings = RuleEngine([_Rule()]).evaluate([client, observed])

    assert len(findings) == 1
    assert findings[0].rule_id == "LP-RULE-TEST-001"


def test_rule_engine_rejects_duplicate_rules_and_unresolvable_citations() -> None:
    with pytest.raises(ValueError, match="unique"):
        RuleEngine([_Rule(), _Rule()])

    class BadRule(_Rule):
        def evaluate(self, context: RuleContext) -> tuple[Finding, ...]:
            return (
                Finding(
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    confidence="possible",
                    cited_sequences=(99,),
                    explanation="Bad citation",
                    next_steps=("Inspect evidence",),
                ),
            )

    with pytest.raises(ValueError, match="citations"):
        RuleEngine([BadRule()]).evaluate([_event("CStoreReceived", {})])


def test_rule_engine_rejects_mismatched_rule_set_version() -> None:
    with pytest.raises(ValueError, match="rule-set version"):
        RuleEngine([_Rule()], rule_set_version="rules-v2").evaluate(
            [_event("AssociationRejected", {"accepted_contexts": ()})]
        )
