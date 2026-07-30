"""Pure domain primitives for deterministic diagnostic conditions."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field

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


ConditionRegistry = ConditionIdRegistry

__all__: tuple[str, ...] = ()
