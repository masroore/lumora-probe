# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Phase 14 seed analysis rule tests."""

from __future__ import annotations

from datetime import UTC, datetime

from lumora_probe.analysis.domain import FindingConfidence
from lumora_probe.analysis.rules import (
    CMoveOutOfBandRule,
    IncompleteStudyRule,
    NoAcceptablePresentationContextRule,
    OversizedDatasetRule,
    RejectedAssociationRule,
    SlowCStoreRule,
    TimeoutRetryRule,
    TransferSyntaxMismatchRule,
    bundled_rules,
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


def test_incomplete_study_rule_reports_missing_instances_as_investigation_target() -> None:
    event = _event(
        {
            "study_uid": "1.2.3.4",
            "expected_instance_count": 5,
            "observed_instance_count": 3,
        },
        sequence=12,
        event_name="StudySummary",
    )

    findings = tuple(IncompleteStudyRule().evaluate(RuleContext((event,), ())))

    assert len(findings) == 1
    assert findings[0].confidence is FindingConfidence.LIKELY
    assert findings[0].cited_sequences == (12,)
    assert "1.2.3.4" in findings[0].explanation
    assert "2 instance(s)" in findings[0].explanation
    assert "problem being investigated" in findings[0].explanation


def test_incomplete_study_rule_uses_instance_set_difference() -> None:
    event = _event(
        {
            "expected_instances": ("sop-1", "sop-2"),
            "observed_instances": ("sop-1",),
        },
        event_name="StudyProjectionUpdated",
    )

    findings = tuple(IncompleteStudyRule().evaluate(RuleContext((event,), ())))

    assert len(findings) == 1
    assert "1 instance(s)" in findings[0].explanation


def test_timeout_retry_rule_detects_pattern_within_association_pair() -> None:
    events = (
        _event({"association_pair_id": "pair-1"}, sequence=13, event_name="AssociationTimeout"),
        _event({"association_pair_id": "pair-1"}, sequence=14, event_name="AssociationRetry"),
        _event({"association_pair_id": "pair-2"}, sequence=15, event_name="AssociationRetry"),
    )

    findings = tuple(TimeoutRetryRule().evaluate(RuleContext(events, ())))

    assert len(findings) == 1
    assert findings[0].cited_sequences == (13, 14)
    assert "pair-1" in findings[0].explanation
    assert "timeout-and-retry" in findings[0].explanation


def test_timeout_retry_rule_accepts_payload_markers() -> None:
    events = (
        _event({"timeout": True}, sequence=16, event_name="WarningRaised"),
        _event({"retry_count": 2}, sequence=17, event_name="WarningRaised"),
    )

    findings = tuple(TimeoutRetryRule().evaluate(RuleContext(events, ())))

    assert len(findings) == 1
    assert findings[0].cited_sequences == (16, 17)


def test_oversized_dataset_rule_uses_configurable_threshold() -> None:
    event = _event(
        {"sop_instance_uid": "1.2.3.4.5", "dataset_size_bytes": 1_001},
        sequence=18,
        event_name="DatasetLoaded",
    )

    findings = tuple(
        OversizedDatasetRule(threshold_bytes=1_000).evaluate(RuleContext((event,), ()))
    )

    assert len(findings) == 1
    assert findings[0].cited_sequences == (18,)
    assert "1.2.3.4.5" in findings[0].explanation
    assert "1,001" not in findings[0].explanation
    assert "1000-byte" in findings[0].explanation


def test_oversized_dataset_rule_ignores_values_at_threshold() -> None:
    event = _event({"bytes": 1_000}, event_name="CStoreReceived")

    assert (
        tuple(OversizedDatasetRule(threshold_bytes=1_000).evaluate(RuleContext((event,), ()))) == ()
    )


def test_c_move_rule_explains_out_of_band_sub_operations_and_remediation() -> None:
    event = _event(
        {"destination_ae_title": "REMOTE-STORE"},
        sequence=19,
        event_name="CMoveRequested",
    )

    findings = tuple(CMoveOutOfBandRule().evaluate(RuleContext((event,), ())))

    assert len(findings) == 1
    assert findings[0].confidence is FindingConfidence.CERTAIN
    assert findings[0].cited_sequences == (19,)
    assert "REMOTE-STORE" in findings[0].explanation
    assert "out-of-band" in findings[0].explanation
    assert "Point the destination AE at Probe" in findings[0].next_steps[0]
    assert "C-GET" in findings[0].next_steps[0]


def test_bundled_rules_contains_all_seed_families_and_accepts_thresholds() -> None:
    rules = bundled_rules(slow_c_store_threshold_ns=10, oversized_dataset_threshold_bytes=20)

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
    slow = next(rule for rule in rules if rule.rule_id == "LP-RULE-PERF-001")
    oversized = next(rule for rule in rules if rule.rule_id == "LP-RULE-DATA-001")
    assert slow.threshold_ns == 10
    assert oversized.threshold_bytes == 20
