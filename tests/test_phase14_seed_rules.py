"""Phase 14 seed analysis rule tests."""

from __future__ import annotations

from datetime import UTC, datetime

from lumora_probe.analysis.domain import FindingConfidence
from lumora_probe.analysis.rules import RejectedAssociationRule
from lumora_probe.analysis.service import RuleContext
from lumora_probe.shared.events import EventEnvelope, EventOrigin, EventSeverity

EVENT_ID = "018f0d4e-7b6a-7000-8000-000000000001"
CORRELATION_ID = "018f0d4e-7b6a-7000-8000-000000000002"


def _event(payload: dict[str, object], *, sequence: int = 7) -> EventEnvelope:
    return EventEnvelope(
        event_id=EVENT_ID,
        event_name="AssociationRejected",
        event_version=1,
        occurred_at=datetime(2026, 7, 30, tzinfo=UTC),
        correlation_id=CORRELATION_ID,
        aggregate_type="Association",
        aggregate_id="association-1",
        producer="test",
        payload=payload,
        origin=EventOrigin.OBSERVED,
        severity=EventSeverity.WARNING,
        monotonic_ns=1,
        sequence=sequence,
    )


def test_rejected_association_rule_requires_result_source_and_reason() -> None:
    event = _event({"result": "0x0122", "source": "remote", "reason": "not authorized"})

    findings = tuple(RejectedAssociationRule().evaluate(RuleContext((event,), ())))

    assert len(findings) == 1
    assert findings[0].confidence is FindingConfidence.CERTAIN
    assert findings[0].cited_sequences == (7,)
    assert "remote" in findings[0].explanation
    assert "0x0122" in findings[0].explanation
    assert "not authorized" in findings[0].explanation


def test_rejected_association_rule_does_not_infer_without_complete_triplet() -> None:
    event = _event({"result": "0x0122", "reason": "not authorized"})

    assert tuple(RejectedAssociationRule().evaluate(RuleContext((event,), ()))) == ()
