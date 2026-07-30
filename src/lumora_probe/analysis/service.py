"""Deterministic observed-condition detection for the analysis slice."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from lumora_probe.shared.events import EventEnvelope, EventOrigin

from .domain import (
    ConditionDefinition,
    ConditionId,
    ConditionIdRegistry,
    ConditionObservation,
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


class ConditionDetector:
    """Normalize mechanically observed facts into diagnostic condition events."""

    def __init__(self, registry: ConditionIdRegistry | None = None) -> None:
        self._registry = registry or default_condition_registry()

    def detect(self, events: Iterable[EventEnvelope]) -> tuple[ConditionObservation, ...]:
        """Return deterministic conditions without mutating or inferring from events."""
        result: list[ConditionObservation] = []
        seen_event_ids: set[str] = set()
        for event in events:
            if event.event_id in seen_event_ids or event.origin is EventOrigin.CLIENT_ASSERTED:
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


__all__: tuple[str, ...] = ()
