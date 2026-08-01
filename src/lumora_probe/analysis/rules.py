# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Bundled deterministic analysis rules."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import cast

from .domain import Finding, FindingConfidence
from .service import AnalysisRule, RuleContext

BUNDLED_RULE_SET_VERSION = "bundled-v1"


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sequence(value: object) -> int | None:
    return value if type(value) is int and not isinstance(value, bool) and value >= 0 else None


def _non_negative_int(value: object) -> int | None:
    return _sequence(value)


def _context_text(value: object) -> str | None:
    if isinstance(value, Mapping):
        context = cast(Mapping[str, object], value)
        sop_class = _text(context.get("sop_class") or context.get("abstract_syntax"))
        transfer_syntaxes = context.get("transfer_syntaxes") or context.get("transfer_syntax")
        if sop_class is not None and transfer_syntaxes:
            return f"{sop_class} ({transfer_syntaxes})"
        return sop_class or _text(context)
    return _text(value)


def _contexts_text(value: object) -> str | None:
    if isinstance(value, (str, bytes)):
        return _text(value)
    if isinstance(value, Iterable):
        values = tuple(
            context
            for context in (_context_text(item) for item in cast(Iterable[object], value))
            if context is not None
        )
        return ", ".join(values) or None
    return _context_text(value)


def _syntax_values(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)):
        text = _text(value)
        return (text,) if text is not None else ()
    if isinstance(value, Mapping):
        context = cast(Mapping[str, object], value)
        nested = (
            context.get("transfer_syntaxes")
            or context.get("transfer_syntax")
            or context.get("accepted_transfer_syntaxes")
            or context.get("accepted_transfer_syntax")
        )
        return _syntax_values(nested)
    if isinstance(value, Iterable):
        values = tuple(
            syntax for item in cast(Iterable[object], value) for syntax in _syntax_values(item)
        )
        return tuple(sorted(set(values)))
    text = _text(value)
    return (text,) if text is not None else ()


def _payload_syntaxes(payload: Mapping[str, object]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    offered = _syntax_values(
        payload.get("offered_transfer_syntaxes")
        or payload.get("offered_transfer_syntax")
        or payload.get("offered_contexts")
    )
    accepted = _syntax_values(
        payload.get("accepted_transfer_syntaxes")
        or payload.get("accepted_transfer_syntax")
        or payload.get("accepted_contexts")
    )
    return offered, accepted


class RejectedAssociationRule:
    """Explain an association rejection when result, source, and reason are observed."""

    rule_id = "LP-RULE-NEG-001"
    rule_version = "1"

    def evaluate(self, context: RuleContext) -> Iterable[Finding]:
        findings: list[Finding] = []
        for event in context.events:
            if event.event_name != "AssociationRejected":
                continue
            result = _text(
                event.payload.get("result")
                or event.payload.get("result_code")
                or event.payload.get("status")
            )
            source = _text(event.payload.get("source") or event.payload.get("rejection_source"))
            reason = _text(event.payload.get("reason"))
            sequence = _sequence(event.sequence)
            if result is None or source is None or reason is None or sequence is None:
                continue
            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    rule_set_version=BUNDLED_RULE_SET_VERSION,
                    confidence=FindingConfidence.CERTAIN,
                    cited_sequences=(sequence,),
                    explanation=(
                        f"The association was rejected by {source} with result {result}: {reason}."
                    ),
                    next_steps=(
                        "Compare the rejection result and source with the peer's negotiation logs.",
                    ),
                )
            )
        return tuple(findings)


class NoAcceptablePresentationContextRule:
    """Explain a rejection where no offered presentation context was accepted."""

    rule_id = "LP-RULE-NEG-002"
    rule_version = "1"

    def evaluate(self, context: RuleContext) -> Iterable[Finding]:
        findings: list[Finding] = []
        for event in context.events:
            if event.event_name != "AssociationRejected":
                continue
            accepted_contexts = event.payload.get("accepted_contexts")
            sop_class = _text(event.payload.get("sop_class") or event.payload.get("sop_class_uid"))
            offered = _contexts_text(
                event.payload.get("offered_contexts")
                or event.payload.get("presentation_contexts")
                or event.payload.get("offered")
            )
            sequence = _sequence(event.sequence)
            if (
                accepted_contexts is None
                or accepted_contexts
                or sop_class is None
                or sequence is None
            ):
                continue
            if offered is None:
                offered = "no offered contexts"
            remediation = (
                f"Offer a presentation context for SOP class {sop_class} with a "
                + "transfer syntax accepted by the peer."
            )
            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    rule_set_version=BUNDLED_RULE_SET_VERSION,
                    confidence=FindingConfidence.CERTAIN,
                    cited_sequences=(sequence,),
                    explanation=(
                        f"No acceptable presentation context was negotiated for SOP class {sop_class}; "
                        f"offered: {offered}."
                    ),
                    next_steps=(remediation,),
                )
            )
        return tuple(findings)


class TransferSyntaxMismatchRule:
    """Explain a negotiated transfer syntax absent from the offered syntaxes."""

    rule_id = "LP-RULE-NEG-003"
    rule_version = "1"

    def evaluate(self, context: RuleContext) -> Iterable[Finding]:
        findings: list[Finding] = []
        for event in context.events:
            offered, accepted = _payload_syntaxes(event.payload)
            sequence = _sequence(event.sequence)
            if not offered or not accepted or set(offered) & set(accepted) or sequence is None:
                continue
            sop_class = (
                _text(event.payload.get("sop_class") or event.payload.get("sop_class_uid"))
                or "the negotiated SOP class"
            )
            offered_text = ", ".join(offered)
            accepted_text = ", ".join(accepted)
            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    rule_set_version=BUNDLED_RULE_SET_VERSION,
                    confidence=FindingConfidence.CERTAIN,
                    cited_sequences=(sequence,),
                    explanation=(
                        f"Transfer syntax mismatch for {sop_class}: offered {offered_text}; "
                        f"accepted {accepted_text}."
                    ),
                    next_steps=(
                        "Offer a transfer syntax supported by the peer, or configure both legs "
                        + "with a common syntax.",
                    ),
                )
            )
        return tuple(findings)


class SlowCStoreRule:
    """Attribute a slow C-STORE observation to its explicitly named leg."""

    rule_id = "LP-RULE-PERF-001"
    rule_version = "1"

    def __init__(self, *, threshold_ns: int = 1_000_000_000) -> None:
        if type(threshold_ns) is not int or isinstance(threshold_ns, bool) or threshold_ns <= 0:
            raise ValueError("threshold_ns must be a positive integer")
        self.threshold_ns = threshold_ns

    def evaluate(self, context: RuleContext) -> Iterable[Finding]:
        findings: list[Finding] = []
        for event in context.events:
            if event.event_name != "CStoreReceived":
                continue
            leg = _text(
                event.payload.get("leg")
                or event.payload.get("leg_name")
                or event.payload.get("direction")
            )
            duration = _non_negative_int(
                event.payload.get("duration_ns")
                or event.payload.get("receive_duration_ns")
                or event.payload.get("transfer_duration_ns")
            )
            if duration is None:
                first = _non_negative_int(event.payload.get("first_monotonic_ns"))
                last = _non_negative_int(event.payload.get("last_monotonic_ns"))
                if first is not None and last is not None and last >= first:
                    duration = last - first
            sequence = _sequence(event.sequence)
            if leg is None or duration is None or duration < self.threshold_ns or sequence is None:
                continue
            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    rule_set_version=BUNDLED_RULE_SET_VERSION,
                    confidence=FindingConfidence.LIKELY,
                    cited_sequences=(sequence,),
                    explanation=(
                        f"The C-STORE duration on the {leg} leg was {duration} ns, above the "
                        f"{self.threshold_ns} ns threshold. This attributes delay to that leg "
                        "without asserting end-to-end modality-to-PACS slowness."
                    ),
                    next_steps=(
                        f"Inspect the {leg} leg's PDU gaps, receive path, and peer timing "
                        + "before comparing it with the other legs.",
                    ),
                )
            )
        return tuple(findings)


class IncompleteStudyRule:
    """Report missing study instances without claiming why the study is incomplete."""

    rule_id = "LP-RULE-STUDY-001"
    rule_version = "1"
    _EVENT_NAMES = frozenset(
        {"StudySummary", "StudyCompleted", "StudyIncomplete", "StudyProjectionUpdated"}
    )

    def evaluate(self, context: RuleContext) -> Iterable[Finding]:
        findings: list[Finding] = []
        for event in context.events:
            if event.event_name not in self._EVENT_NAMES:
                continue
            payload = event.payload
            missing = payload.get("missing_instances")
            missing_count = (
                len(tuple(cast(Iterable[object], missing)))
                if isinstance(missing, (tuple, list, set, frozenset))
                else 0
            )
            expected = payload.get("expected_instance_count")
            observed = payload.get("observed_instance_count")
            if (
                type(expected) is int
                and not isinstance(expected, bool)
                and type(observed) is int
                and not isinstance(observed, bool)
                and expected > observed
            ):
                missing_count = max(missing_count, expected - observed)
            expected_instances = payload.get("expected_instances")
            observed_instances = payload.get("observed_instances")
            if isinstance(expected_instances, Iterable) and isinstance(
                observed_instances, Iterable
            ):
                expected_set: set[object] = set(cast(Iterable[object], expected_instances))
                observed_set: set[object] = set(cast(Iterable[object], observed_instances))
                missing_count = max(missing_count, len(expected_set - observed_set))
            sequence = _sequence(event.sequence)
            if missing_count <= 0 or sequence is None:
                continue
            study_uid = _text(payload.get("study_uid") or payload.get("study_id"))
            study_label = f"study {study_uid}" if study_uid is not None else "the study"
            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    rule_set_version=BUNDLED_RULE_SET_VERSION,
                    confidence=FindingConfidence.LIKELY,
                    cited_sequences=(sequence,),
                    explanation=(
                        f"{study_label.capitalize()} appears incomplete: {missing_count} "
                        + "instance(s) are missing from the observed evidence. This identifies "
                        + "the problem being investigated, not its cause."
                    ),
                    next_steps=(
                        "Compare the expected instance list with the sender, association, and "
                        + "capture boundaries before concluding where data was lost.",
                    ),
                )
            )
        return tuple(findings)


class TimeoutRetryRule:
    """Detect a timeout followed by retry evidence within one association pair."""

    rule_id = "LP-RULE-ASSOC-001"
    rule_version = "1"

    @staticmethod
    def _pair_key(event: object) -> str:
        payload = getattr(event, "payload", {})
        values: Mapping[str, object] = (
            cast(Mapping[str, object], payload) if isinstance(payload, Mapping) else {}
        )
        pair = _text(values.get("association_pair_id") or values.get("association_id"))
        return pair or str(getattr(event, "correlation_id", "unknown"))

    @staticmethod
    def _kind(event: object) -> str | None:
        name = str(getattr(event, "event_name", "")).casefold()
        payload = getattr(event, "payload", {})
        values: Mapping[str, object] = (
            cast(Mapping[str, object], payload) if isinstance(payload, Mapping) else {}
        )
        if (
            "timeout" in name
            or name == "timedout"
            or values.get("timeout") is True
            or values.get("timed_out") is True
        ):
            return "timeout"
        retry_count = values.get("retry_count")
        if (
            "retry" in name
            or values.get("retry") is True
            or (type(retry_count) is int and not isinstance(retry_count, bool) and retry_count > 0)
        ):
            return "retry"
        return None

    def evaluate(self, context: RuleContext) -> Iterable[Finding]:
        grouped: dict[str, dict[str, list[int]]] = {}
        for event in context.events:
            kind = self._kind(event)
            sequence = _sequence(event.sequence)
            if kind is None or sequence is None:
                continue
            pair = grouped.setdefault(self._pair_key(event), {"timeout": [], "retry": []})
            pair[kind].append(sequence)

        findings: list[Finding] = []
        for pair_id, values in sorted(grouped.items()):
            if not values["timeout"] or not values["retry"]:
                continue
            sequences = tuple(sorted(set(values["timeout"] + values["retry"])))
            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    rule_set_version=BUNDLED_RULE_SET_VERSION,
                    confidence=FindingConfidence.LIKELY,
                    cited_sequences=sequences,
                    explanation=(
                        f"Association pair {pair_id} contains {len(values['timeout'])} timeout "
                        f"event(s) and {len(values['retry'])} retry event(s), indicating a "
                        + "timeout-and-retry pattern."
                    ),
                    next_steps=(
                        "Compare timeout intervals, retry policy, and the last observed event on "
                        + "each association leg.",
                    ),
                )
            )
        return tuple(findings)


class OversizedDatasetRule:
    """Flag an observed dataset whose size exceeds a configured byte threshold."""

    rule_id = "LP-RULE-DATA-001"
    rule_version = "1"
    _EVENT_NAMES = frozenset({"CStoreReceived", "DatasetLoaded", "InstancePersisted"})

    def __init__(self, *, threshold_bytes: int = 100_000_000) -> None:
        if (
            type(threshold_bytes) is not int
            or isinstance(threshold_bytes, bool)
            or threshold_bytes <= 0
        ):
            raise ValueError("threshold_bytes must be a positive integer")
        self.threshold_bytes = threshold_bytes

    def evaluate(self, context: RuleContext) -> Iterable[Finding]:
        findings: list[Finding] = []
        for event in context.events:
            if event.event_name not in self._EVENT_NAMES:
                continue
            size_bytes = _non_negative_int(
                event.payload.get("size_bytes")
                or event.payload.get("dataset_size_bytes")
                or event.payload.get("bytes")
            )
            sequence = _sequence(event.sequence)
            if size_bytes is None or size_bytes <= self.threshold_bytes or sequence is None:
                continue
            instance = _text(
                event.payload.get("sop_instance_uid") or event.payload.get("instance_id")
            )
            subject = f"instance {instance}" if instance is not None else "the dataset"
            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    rule_set_version=BUNDLED_RULE_SET_VERSION,
                    confidence=FindingConfidence.LIKELY,
                    cited_sequences=(sequence,),
                    explanation=(
                        f"{subject.capitalize()} is {size_bytes} bytes, above the configured "
                        f"{self.threshold_bytes}-byte dataset threshold."
                    ),
                    next_steps=(
                        "Confirm the expected object size, transfer syntax, and peer limits "
                        + "before changing the threshold or transport configuration.",
                    ),
                )
            )
        return tuple(findings)


class CMoveOutOfBandRule:
    """Explain that C-MOVE sub-operations flow outside Probe's observed path."""

    rule_id = "LP-RULE-DIMSE-001"
    rule_version = "1"

    def evaluate(self, context: RuleContext) -> Iterable[Finding]:
        findings: list[Finding] = []
        for event in context.events:
            if event.event_name != "CMoveRequested":
                continue
            sequence = _sequence(event.sequence)
            if sequence is None:
                continue
            destination = (
                _text(
                    event.payload.get("destination_ae")
                    or event.payload.get("destination_ae_title")
                    or event.payload.get("move_destination")
                )
                or "the configured destination AE"
            )
            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    rule_set_version=BUNDLED_RULE_SET_VERSION,
                    confidence=FindingConfidence.CERTAIN,
                    cited_sequences=(sequence,),
                    explanation=(
                        f"C-MOVE sub-operation data flows out-of-band from Probe to {destination}; "
                        + "the subsequent C-STORE operations do not traverse this capture path."
                    ),
                    next_steps=(
                        "Point the destination AE at Probe to observe the sub-operations, or use "
                        + "C-GET when the workflow requires data to remain on this association.",
                    ),
                )
            )
        return tuple(findings)


def bundled_rules(
    *,
    slow_c_store_threshold_ns: int = 1_000_000_000,
    oversized_dataset_threshold_bytes: int = 100_000_000,
) -> tuple[AnalysisRule, ...]:
    """Build the deterministic bundled seed rule set with configured thresholds."""

    return (
        RejectedAssociationRule(),
        NoAcceptablePresentationContextRule(),
        TransferSyntaxMismatchRule(),
        SlowCStoreRule(threshold_ns=slow_c_store_threshold_ns),
        IncompleteStudyRule(),
        TimeoutRetryRule(),
        OversizedDatasetRule(threshold_bytes=oversized_dataset_threshold_bytes),
        CMoveOutOfBandRule(),
    )


__all__: tuple[str, ...] = ()
