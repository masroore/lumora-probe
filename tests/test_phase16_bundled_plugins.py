"""Phase 16 proof that seed analyzers run through the public plugin SDK."""

from __future__ import annotations

from datetime import UTC, datetime

from lumora_probe.analysis.service import RuleEngine
from lumora_probe.plugins.bundled_rules import (
    BUNDLED_RULE_SET_VERSION,
    bundled_plugin,
    bundled_rules,
)
from lumora_probe.plugins.contracts import AnalysisContextDTO, EventDTO
from lumora_probe.shared.events import EventEnvelope, EventOrigin, EventSeverity


def _event(
    payload: dict[str, object], *, sequence: int = 7, event_name: str = "AssociationRejected"
) -> EventDTO:
    return EventDTO(
        event_id=f"event-{sequence}",
        event_name=event_name,
        event_version=1,
        sequence=sequence,
        aggregate_type="Association",
        aggregate_id="association-1",
        producer="test",
        payload=payload,
        origin="observed",
    )


def test_bundled_seed_rules_are_public_sdk_analyzers() -> None:
    rules = bundled_rules(slow_c_store_threshold_ns=1_000, oversized_dataset_threshold_bytes=1_000)

    assert len(rules) == 8
    assert {rule.rule_id for rule in rules} == {
        "LP-RULE-NEG-001",
        "LP-RULE-NEG-002",
        "LP-RULE-NEG-003",
        "LP-RULE-PERF-001",
        "LP-RULE-STUDY-001",
        "LP-RULE-ASSOC-001",
        "LP-RULE-DATA-001",
        "LP-RULE-DIMSE-001",
    }
    findings = tuple(
        bundled_plugin.analyze(
            AnalysisContextDTO(
                events=(_event({"result": "0x0122", "source": "remote", "reason": "denied"}),)
            )
        )
    )
    assert len(findings) == 1
    assert findings[0].rule_set_version == BUNDLED_RULE_SET_VERSION
    assert findings[0].cited_sequences == (7,)


def test_rule_engine_accepts_bundled_plugin_through_public_sdk_adapter() -> None:
    event = EventEnvelope(
        event_id="018f0d4e-7b6a-7000-8000-000000000001",
        event_name="AssociationRejected",
        event_version=1,
        occurred_at=datetime(2026, 7, 30, tzinfo=UTC),
        correlation_id="018f0d4e-7b6a-7000-8000-000000000002",
        aggregate_type="Association",
        aggregate_id="association-1",
        producer="test",
        payload={"result": "0x0122", "source": "remote", "reason": "denied"},
        origin=EventOrigin.OBSERVED,
        severity=EventSeverity.WARNING,
        monotonic_ns=1,
        sequence=7,
    )

    findings = RuleEngine((), rule_set_version=BUNDLED_RULE_SET_VERSION).evaluate_plugin(
        bundled_plugin.analyze, (event,)
    )

    assert len(findings) == 1
    assert findings[0].rule_id == "LP-RULE-NEG-001"
