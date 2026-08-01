# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Pure domain primitives for deterministic diagnostic conditions."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from lumora_probe.shared.errors import domain_invariant

_CONDITION_ID_PATTERN = re.compile(r"^LP-[A-Z]{3}-([0-9]{3})$")


@dataclass(frozen=True, slots=True)
class ConditionId:
    """Stable three-part diagnostic condition identifier."""

    value: str

    def __post_init__(self) -> None:
        match = _CONDITION_ID_PATTERN.fullmatch(self.value) if type(self.value) is str else None
        if match is None or int(match.group(1)) == 0:
            raise domain_invariant(
                "condition ID must match LP-XXX-NNN",
                field="value",
                value=self.value,
                remediation="Use the next unused three-letter namespace and three-digit number.",
            )

    @classmethod
    def from_parts(cls, namespace: str, number: int) -> ConditionId:
        """Build a condition ID from its documented namespace and sequence."""
        if type(namespace) is not str or re.fullmatch(r"[A-Z]{3}", namespace) is None:
            raise domain_invariant(
                "condition namespace must contain three uppercase ASCII letters",
                field="namespace",
                value=namespace,
            )
        if type(number) is not int or isinstance(number, bool) or not 1 <= number <= 999:
            raise domain_invariant(
                "condition number must be an integer from 1 through 999",
                field="number",
                value=number,
            )
        return cls(f"LP-{namespace}-{number:03d}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ConditionDefinition:
    """Human-readable metadata registered for one diagnostic condition."""

    condition_id: ConditionId | str
    name: str
    description: str
    remediation: str

    def as_dict(self) -> dict[str, str]:
        """Return the stable catalogue representation."""
        condition_id = self.condition_id
        if not isinstance(condition_id, ConditionId):
            raise TypeError("condition definition ID was not validated")
        return {
            "code": condition_id.value,
            "name": self.name,
            "description": self.description,
            "remediation": self.remediation,
        }

    def __post_init__(self) -> None:
        if isinstance(self.condition_id, str):
            object.__setattr__(self, "condition_id", ConditionId(self.condition_id))
        elif type(self.condition_id) is not ConditionId:
            raise domain_invariant(
                "condition_id must be a ConditionId or string",
                field="condition_id",
                value=self.condition_id,
            )
        for field_name, value in (
            ("name", self.name),
            ("description", self.description),
            ("remediation", self.remediation),
        ):
            if type(value) is not str or not value.strip():
                raise domain_invariant(
                    f"{field_name} must be a non-empty string",
                    field=field_name,
                    value=value,
                )
            object.__setattr__(self, field_name, value.strip())


class ConditionIdRegistry:
    """Deterministic registry that prevents condition ID reuse."""

    def __init__(self, definitions: Iterable[ConditionDefinition] = ()) -> None:
        self._definitions: dict[ConditionId, ConditionDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: ConditionDefinition) -> None:
        """Register one ID exactly once; duplicate IDs are rejected."""
        if type(definition) is not ConditionDefinition:
            raise domain_invariant(
                "registry entries must be ConditionDefinition values",
                field="definition",
                value=definition,
            )
        condition_id = definition.condition_id
        if not isinstance(condition_id, ConditionId):
            raise domain_invariant(
                "condition definition must contain a validated ConditionId",
                field="condition_id",
                value=condition_id,
            )
        if condition_id in self._definitions:
            raise domain_invariant(
                "condition ID is already registered and cannot be reused",
                field="condition_id",
                value=condition_id.value,
            )
        self._definitions[condition_id] = definition

    def get(self, condition_id: ConditionId | str) -> ConditionDefinition | None:
        """Return a registered definition, or ``None`` when it is unknown."""
        if isinstance(condition_id, ConditionId):
            key = condition_id
        else:
            key = ConditionId(condition_id)
        return self._definitions.get(key)

    def require(self, condition_id: ConditionId | str) -> ConditionDefinition:
        """Return a definition or raise a structured invariant error."""
        definition = self.get(condition_id)
        if definition is None:
            value = condition_id.value if isinstance(condition_id, ConditionId) else condition_id
            raise domain_invariant(
                "condition ID is not registered",
                field="condition_id",
                value=value,
            )
        return definition

    def ids(self) -> tuple[ConditionId, ...]:
        """Return registered IDs in stable lexical order."""
        return tuple(sorted(self._definitions, key=lambda condition_id: condition_id.value))

    def definitions(self) -> tuple[ConditionDefinition, ...]:
        """Return registered definitions in stable ID order."""
        return tuple(self._definitions[condition_id] for condition_id in self.ids())

    def catalog(self) -> dict[str, object]:
        """Return the versioned, JSON-compatible condition catalogue."""
        return {
            "catalog_version": 1,
            "allocation": "LP-XXX-NNN; XXX is a three-letter namespace; NNN is never reused and ranges from 001 through 999.",
            "conditions": [definition.as_dict() for definition in self.definitions()],
        }

    def __contains__(self, condition_id: object) -> bool:
        return isinstance(condition_id, ConditionId) and condition_id in self._definitions

    def __iter__(self) -> Iterator[ConditionDefinition]:
        return iter(self.definitions())

    def __len__(self) -> int:
        return len(self._definitions)


@dataclass(frozen=True, slots=True)
class ConditionObservation:
    """Deterministic observed condition normalized into a diagnostic event payload."""

    condition_id: ConditionId | str
    event_name: str
    source_event_id: str
    source_sequence: int | None
    aggregate_id: str
    message: str
    details: Mapping[str, object] = field(default_factory=dict[str, object])

    def __post_init__(self) -> None:
        if isinstance(self.condition_id, str):
            object.__setattr__(self, "condition_id", ConditionId(self.condition_id))
        elif type(self.condition_id) is not ConditionId:
            raise domain_invariant(
                "condition_id must be a ConditionId or string",
                field="condition_id",
                value=self.condition_id,
            )
        if self.event_name not in {"WarningRaised", "ErrorRaised"}:
            raise domain_invariant(
                "condition event must be WarningRaised or ErrorRaised",
                field="event_name",
                value=self.event_name,
            )
        for field_name, value in (
            ("source_event_id", self.source_event_id),
            ("aggregate_id", self.aggregate_id),
            ("message", self.message),
        ):
            if type(value) is not str or not value.strip():
                raise domain_invariant(
                    f"{field_name} must be a non-empty string",
                    field=field_name,
                    value=value,
                )
            object.__setattr__(self, field_name, value.strip())
        if self.source_sequence is not None and (
            type(self.source_sequence) is not int or self.source_sequence < 0
        ):
            raise domain_invariant(
                "source_sequence must be a non-negative integer or None",
                field="source_sequence",
                value=self.source_sequence,
            )
        object.__setattr__(self, "details", dict(self.details))

    @property
    def code(self) -> str:
        """Return the stable condition code used by WarningRaised/ErrorRaised."""
        condition_id = self.condition_id
        if not isinstance(condition_id, ConditionId):
            raise TypeError("condition observation ID was not validated")
        return condition_id.value

    def as_payload(self, *, name: str) -> dict[str, object]:
        """Return the normalized diagnostic event payload."""
        return {
            "code": self.code,
            "condition_name": name,
            "message": self.message,
            "source_event_id": self.source_event_id,
            "source_sequence": self.source_sequence,
            "details": dict(self.details),
        }


class FindingConfidence(StrEnum):
    """Coarse calibrated confidence vocabulary for inferred findings."""

    CERTAIN = "certain"
    LIKELY = "likely"
    POSSIBLE = "possible"


@dataclass(frozen=True, slots=True)
class Finding:
    """Versioned, evidence-linked inference derived from captured observations."""

    rule_id: str
    rule_version: str
    confidence: FindingConfidence | str
    cited_sequences: tuple[int, ...] | Iterable[int]
    explanation: str
    next_steps: tuple[str, ...] | Iterable[str]
    rule_set_version: str = "bundled-v1"

    def __post_init__(self) -> None:
        for field_name, value in (
            ("rule_id", self.rule_id),
            ("rule_version", self.rule_version),
            ("rule_set_version", self.rule_set_version),
        ):
            if type(value) is not str or not value.strip():
                raise domain_invariant(
                    f"{field_name} must be a non-empty string",
                    field=field_name,
                    value=value,
                )
            object.__setattr__(self, field_name, value.strip())
        if type(self.confidence) is str:
            try:
                confidence = FindingConfidence(self.confidence)
            except ValueError as exc:
                raise domain_invariant(
                    "confidence must be certain, likely, or possible",
                    field="confidence",
                    value=self.confidence,
                ) from exc
            object.__setattr__(self, "confidence", confidence)
        elif type(self.confidence) is not FindingConfidence:
            raise domain_invariant(
                "confidence must use the coarse FindingConfidence vocabulary",
                field="confidence",
                value=self.confidence,
            )

        sequences = tuple(self.cited_sequences)
        if not sequences or any(
            type(sequence) is not int or isinstance(sequence, bool) or sequence < 0
            for sequence in sequences
        ):
            raise domain_invariant(
                "cited_sequences must contain at least one non-negative integer",
                field="cited_sequences",
                value=sequences,
            )
        if sequences != tuple(sorted(set(sequences))):
            raise domain_invariant(
                "cited_sequences must be unique and sorted",
                field="cited_sequences",
                value=sequences,
            )
        object.__setattr__(self, "cited_sequences", sequences)

        if type(self.explanation) is not str or not self.explanation.strip():
            raise domain_invariant(
                "explanation must be a non-empty string",
                field="explanation",
                value=self.explanation,
            )
        object.__setattr__(self, "explanation", self.explanation.strip())
        steps = tuple(self.next_steps)
        if not steps or any(type(step) is not str or not step.strip() for step in steps):
            raise domain_invariant(
                "next_steps must contain at least one non-empty string",
                field="next_steps",
                value=steps,
            )
        object.__setattr__(self, "next_steps", tuple(step.strip() for step in steps))

    @property
    def sequence_numbers(self) -> tuple[int, ...]:
        """Return cited event sequence numbers for UI and report consumers."""
        return tuple(self.cited_sequences)

    def as_dict(self) -> dict[str, object]:
        """Return the stable JSON representation of the finding."""
        confidence = self.confidence
        confidence_value = (
            confidence.value
            if isinstance(confidence, FindingConfidence)
            else FindingConfidence(confidence).value
        )
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "rule_set_version": self.rule_set_version,
            "confidence": confidence_value,
            "cited_sequences": list(self.cited_sequences),
            "explanation": self.explanation,
            "next_steps": list(self.next_steps),
        }


ConditionRegistry = ConditionIdRegistry

__all__: tuple[str, ...] = ()
