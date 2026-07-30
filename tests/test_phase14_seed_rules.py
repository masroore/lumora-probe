"""Phase 14 seed analysis rule tests."""

from __future__ import annotations

from datetime import UTC, datetime

from lumora_probe.analysis.domain import FindingConfidence
from lumora_probe.analysis.rules import (
    NoAcceptablePresentationContextRule,
    RejectedAssociationRule,
    SlowCStoreRule,
    TransferSyntaxMismatchRule,
)
from lumora_probe.analysis.service import RuleContext
from lumora_probe.shared.events import EventEnvelope, EventOrigin, EventSeverity

EVENT_ID = "018f0d4e-7b6a-7000-8000-000000000001"
CORRELATION_ID = "018f0d4e-7b6a-7000-8000-000000000002"


def _event(
    payload: dict[str, object], *, sequence: int = 7, event_name: str = "AssociationRejected"
) -> EventEnvelope:
    return EventEnvelope(
        event_id=EVENT_ID,
        event_name=event_name,
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


def test_no_acceptable_context_rule_names_sop_class_and_offered_contexts() -> None:
    event = _event(
        {
            "accepted_contexts": (),
            "sop_class": "1.2.840.10008.5.1.4.1.1.2",
            "offered_contexts": (
                {
                    "sop_class": "1.2.840.10008.5.1.4.1.1.2",
                    "transfer_syntaxes": ("1.2.840.10008.1.2.1",),
                },
            ),
        },
        sequence=8,
    )

    findings = tuple(NoAcceptablePresentationContextRule().evaluate(RuleContext((event,), ())))

    assert len(findings) == 1
    assert findings[0].cited_sequences == (8,)
    assert "1.2.840.10008.5.1.4.1.1.2" in findings[0].explanation
    assert "1.2.840.10008.1.2.1" in findings[0].explanation
    assert "Offer a presentation context" in findings[0].next_steps[0]


def test_no_acceptable_context_rule_skips_accepted_contexts() -> None:
    event = _event(
        {
            "accepted_contexts": ({"sop_class": "1.2.3"},),
            "sop_class": "1.2.3",
            "offered_contexts": ({"sop_class": "1.2.3"},),
        }
    )

    assert tuple(NoAcceptablePresentationContextRule().evaluate(RuleContext((event,), ()))) == ()


def test_transfer_syntax_mismatch_rule_reports_offered_and_accepted_values() -> None:
    event = _event(
        {
            "sop_class": "1.2.3",
            "offered_transfer_syntaxes": ("1.2.840.10008.1.2.1",),
            "accepted_transfer_syntax": "1.2.840.10008.1.2.2",
        },
        sequence=9,
    )

    findings = tuple(TransferSyntaxMismatchRule().evaluate(RuleContext((event,), ())))

    assert len(findings) == 1
    assert findings[0].cited_sequences == (9,)
    assert "offered 1.2.840.10008.1.2.1" in findings[0].explanation
    assert "accepted 1.2.840.10008.1.2.2" in findings[0].explanation
    assert "common syntax" in findings[0].next_steps[0]


def test_transfer_syntax_mismatch_rule_ignores_common_syntax() -> None:
    event = _event(
        {
            "offered_transfer_syntaxes": ("1.2.840.10008.1.2.1",),
            "accepted_transfer_syntax": "1.2.840.10008.1.2.1",
        }
    )

    assert tuple(TransferSyntaxMismatchRule().evaluate(RuleContext((event,), ()))) == ()


def test_slow_c_store_rule_attributes_delay_to_one_leg() -> None:
    events = (
        _event(
            {"leg": "downstream", "duration_ns": 2_000},
            sequence=10,
            event_name="CStoreReceived",
        ),
        _event(
            {"leg": "upstream", "duration_ns": 100},
            sequence=11,
            event_name="CStoreReceived",
        ),
    )

    findings = tuple(SlowCStoreRule(threshold_ns=1_000).evaluate(RuleContext(events, ())))

    assert len(findings) == 1
    assert findings[0].confidence is FindingConfidence.LIKELY
    assert findings[0].cited_sequences == (10,)
    assert "downstream leg" in findings[0].explanation
    assert "end-to-end" in findings[0].explanation


def test_slow_c_store_rule_can_derive_duration_from_monotonic_summary() -> None:
    event = _event(
        {"leg_name": "probe-hop", "first_monotonic_ns": 100, "last_monotonic_ns": 1_500},
        event_name="CStoreReceived",
    )

    findings = tuple(SlowCStoreRule(threshold_ns=1_000).evaluate(RuleContext((event,), ())))

    assert len(findings) == 1
    assert "probe-hop leg" in findings[0].explanation
