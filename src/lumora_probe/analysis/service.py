# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Deterministic observed-condition detection for the analysis slice."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from lumora_probe.plugins.contracts import AnalysisContextDTO, EventDTO, FindingDTO
from lumora_probe.shared.events import EventEnvelope, EventOrigin

from .domain import (
    ConditionDefinition,
    ConditionId,
    ConditionIdRegistry,
    ConditionObservation,
    Finding,
)

DEFAULT_CONDITION_DEFINITIONS = (
    ConditionDefinition(
        condition_id="LP-NEG-001",
        name="Association rejected",
        description="The observed association negotiation was rejected.",
        remediation="Compare the rejection result, source, reason, and offered contexts with the peer configuration.",
    ),
    ConditionDefinition(
        condition_id="LP-NEG-002",
        name="Association aborted",
        description="The observed association was aborted before normal release.",
        remediation="Inspect the abort source and the last observed protocol events on both legs.",
    ),
    ConditionDefinition(
        condition_id="LP-NEG-004",
        name="No acceptable presentation context",
        description="No acceptable presentation context was observed for the association.",
        remediation="Offer a presentation context containing the SOP class and a transfer syntax accepted by the peer.",
    ),
)


def default_condition_registry() -> ConditionIdRegistry:
    """Build a fresh registry for the bundled observed-condition definitions."""
    return ConditionIdRegistry(DEFAULT_CONDITION_DEFINITIONS)


def _observed_events(events: Iterable[EventEnvelope]) -> tuple[EventEnvelope, ...]:
    """Return only server-observed evidence admitted to analysis."""

    return tuple(event for event in events if event.origin is EventOrigin.OBSERVED)


class ConditionDetector:
    """Normalize mechanically observed facts into diagnostic condition events."""

    def __init__(self, registry: ConditionIdRegistry | None = None) -> None:
        self._registry = registry or default_condition_registry()

    def detect(self, events: Iterable[EventEnvelope]) -> tuple[ConditionObservation, ...]:
        """Return deterministic conditions without mutating or inferring from events."""
        result: list[ConditionObservation] = []
        seen_event_ids: set[str] = set()
        for event in _observed_events(events):
            if event.event_id in seen_event_ids:
                continue
            seen_event_ids.add(event.event_id)
            observation = self._detect_one(event)
            if observation is not None:
                result.append(observation)
        return tuple(result)

    def _detect_one(self, event: EventEnvelope) -> ConditionObservation | None:
        code = self._code_for(event)
        if code is None:
            return None
        definition = self._registry.get(code)
        if definition is None:
            return None
        payload = event.payload
        reason = payload.get("reason")
        message = (
            reason.strip() if isinstance(reason, str) and reason.strip() else definition.description
        )
        details = {
            key: value
            for key, value in payload.items()
            if key not in {"code", "condition_code", "reason"}
        }
        event_name = (
            "ErrorRaised" if event.severity.value in {"error", "critical"} else "WarningRaised"
        )
        if event.event_name in {"WarningRaised", "ErrorRaised"}:
            event_name = event.event_name
        return ConditionObservation(
            condition_id=code,
            event_name=event_name,
            source_event_id=event.event_id,
            source_sequence=event.sequence,
            aggregate_id=event.aggregate_id,
            message=message,
            details=details,
        )

    def _code_for(self, event: EventEnvelope) -> ConditionId | str | None:
        payload: Mapping[str, Any] = event.payload
        explicit_code = payload.get("condition_code") or payload.get("code")
        if isinstance(explicit_code, str):
            return explicit_code
        if event.event_name == "AssociationRejected":
            accepted_contexts = payload.get("accepted_contexts")
            return "LP-NEG-004" if not accepted_contexts else "LP-NEG-001"
        if event.event_name == "AssociationAborted":
            return "LP-NEG-002"
        return None


@dataclass(frozen=True, slots=True)
class RuleContext:
    """Immutable observed evidence and deterministic conditions supplied to a rule."""

    events: tuple[EventEnvelope, ...]
    conditions: tuple[ConditionObservation, ...]


class AnalysisRule(Protocol):
    """Public shape for bundled and plugin-contributed analysis rules."""

    rule_id: str
    rule_version: str

    def evaluate(self, context: RuleContext) -> Iterable[Finding]: ...


class RuleEngine:
    """Evaluate versioned rules deterministically against observed evidence."""

    def __init__(
        self,
        rules: Iterable[AnalysisRule],
        *,
        detector: ConditionDetector | None = None,
        rule_set_version: str = "bundled-v1",
    ) -> None:
        values = tuple(rules)
        keys = [(rule.rule_id, rule.rule_version) for rule in values]
        if len(keys) != len(set(keys)):
            raise ValueError("rule IDs and versions must be unique")
        if type(rule_set_version) is not str or not rule_set_version.strip():
            raise ValueError("rule_set_version must be a non-empty string")
        self._rules = tuple(sorted(values, key=lambda rule: (rule.rule_id, rule.rule_version)))
        self._rule_set_version = rule_set_version.strip()
        self._detector = detector or ConditionDetector()

    def evaluate(self, events: Iterable[EventEnvelope]) -> tuple[Finding, ...]:
        """Return findings sorted by rule identity and cited evidence."""
        observed = _observed_events(events)
        context = RuleContext(
            events=observed,
            conditions=self._detector.detect(observed),
        )
        sequences = {event.sequence for event in observed if event.sequence is not None}
        findings: list[Finding] = []
        for rule in self._rules:
            for finding in rule.evaluate(context):
                if type(finding) is not Finding:
                    raise TypeError("analysis rules must return Finding values")
                if (finding.rule_id, finding.rule_version) != (
                    rule.rule_id,
                    rule.rule_version,
                ):
                    raise ValueError("finding rule identity must match its evaluating rule")
                if finding.rule_set_version != self._rule_set_version:
                    raise ValueError("finding rule-set version must match the evaluating rule set")
                if not set(finding.cited_sequences).issubset(sequences):
                    raise ValueError("finding citations must resolve to observed event sequences")
                findings.append(finding)
        return tuple(
            sorted(
                findings,
                key=lambda finding: (
                    finding.rule_id,
                    finding.rule_version,
                    finding.cited_sequences,
                    finding.explanation,
                ),
            )
        )

    def evaluate_plugin(
        self,
        analyzer: Callable[[AnalysisContextDTO], Iterable[FindingDTO]],
        events: Iterable[EventEnvelope],
    ) -> tuple[Finding, ...]:
        """Evaluate a public-SDK analyzer and apply the same evidence validation."""

        observed = _observed_events(events)
        context = AnalysisContextDTO(
            events=tuple(
                EventDTO(
                    event_id=event.event_id,
                    event_name=event.event_name,
                    event_version=event.event_version,
                    sequence=event.sequence,
                    aggregate_type=event.aggregate_type,
                    aggregate_id=event.aggregate_id,
                    producer=event.producer,
                    payload=event.payload,
                    origin=event.origin.value,
                )
                for event in observed
            )
        )
        sequences = {event.sequence for event in observed if event.sequence is not None}
        findings: list[Finding] = []
        for contribution in analyzer(context):
            if type(contribution) is not FindingDTO:
                raise TypeError("plugin analyzers must return FindingDTO values")
            if not set(contribution.cited_sequences).issubset(sequences):
                raise ValueError(
                    "plugin finding citations must resolve to observed event sequences"
                )
            findings.append(
                Finding(
                    rule_id=contribution.rule_id,
                    rule_version=contribution.rule_version,
                    rule_set_version=contribution.rule_set_version,
                    confidence=contribution.confidence,
                    cited_sequences=contribution.cited_sequences,
                    explanation=contribution.explanation,
                    next_steps=contribution.next_steps,
                )
            )
        return tuple(
            sorted(
                findings,
                key=lambda finding: (
                    finding.rule_id,
                    finding.rule_version,
                    finding.cited_sequences,
                    finding.explanation,
                ),
            )
        )

    run = evaluate


__all__: tuple[str, ...] = ()
