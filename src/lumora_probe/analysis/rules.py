"""Bundled deterministic analysis rules."""

from __future__ import annotations

from collections.abc import Iterable

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


__all__: tuple[str, ...] = ()
