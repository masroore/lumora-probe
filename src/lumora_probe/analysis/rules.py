"""Bundled deterministic analysis rules."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import cast

from .domain import Finding, FindingConfidence
from .service import RuleContext

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


__all__: tuple[str, ...] = ()
