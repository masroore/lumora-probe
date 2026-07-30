"""Versioned event contracts and payload registry for Lumora Probe."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, ClassVar, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from lumora_probe.core.config import is_uuid7

EVENT_CATALOG_VERSION = 1


class EventClock(Protocol):
    """Minimal injected clock contract used by the event boundary."""

    def now(self) -> datetime: ...

    def monotonic_ns(self) -> int: ...


class EventIdGenerator(Protocol):
    """Minimal injected identity contract used by the event boundary."""

    def new_id(self) -> str: ...


class EventCategory(StrEnum):
    """The ten normative event categories."""

    ASSOCIATION = "Association"
    DIMSE = "DIMSE"
    DATASET = "Dataset"
    VIEWER = "Viewer"
    CAPTURE = "Capture"
    REPLAY = "Replay"
    ANALYSIS = "Analysis"
    REPORTING = "Reporting"
    PLUGIN = "Plugin"
    SYSTEM = "System"


class EventOrigin(StrEnum):
    """Whether an event was observed by the server or asserted by the browser."""

    OBSERVED = "observed"
    CLIENT_ASSERTED = "client-asserted"


class EventSeverity(StrEnum):
    """Operator-facing event severity."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventPayload(BaseModel):
    """Default open payload model for events without a narrower schema."""

    model_config = ConfigDict(extra="allow", frozen=True)


class UnknownEventPayload(EventPayload):
    """Opaque payload for a future event name or version."""


_EVENT_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_RESERVED_IMPERATIVE_PREFIXES = (
    "Start",
    "Stop",
    "Accept",
    "Reject",
    "Release",
    "Abort",
    "Parse",
    "Load",
    "Do",
    "Request",
    "Create",
    "Delete",
    "Update",
    "Set",
)


class EventEnvelope(BaseModel):
    """Immutable, versioned wire envelope shared by all event producers."""

    model_config = ConfigDict(extra="allow", frozen=True)

    event_id: str
    event_name: str
    event_version: int = Field(ge=1)
    occurred_at: datetime
    correlation_id: str
    causation_id: str | None = None
    aggregate_type: str
    aggregate_id: str
    producer: str
    severity: EventSeverity = EventSeverity.INFO
    payload: dict[str, Any]
    origin: EventOrigin
    monotonic_ns: int = Field(ge=0)
    sequence: int | None = Field(default=None, ge=0)
    replay_id: str | None = None
    replay_of_event_id: str | None = None

    _UUID7_FIELDS: ClassVar[tuple[str, ...]] = (
        "event_id",
        "correlation_id",
        "causation_id",
        "replay_id",
        "replay_of_event_id",
    )

    @field_validator(
        "event_id", "correlation_id", "causation_id", "replay_id", "replay_of_event_id"
    )
    @classmethod
    def validate_uuid7(cls, value: str | None) -> str | None:
        if value is not None and not is_uuid7(value):
            raise ValueError("event identity fields must be UUIDv7 values")
        return value

    @field_validator("event_name")
    @classmethod
    def validate_event_name(cls, value: str) -> str:
        if not _EVENT_NAME_RE.fullmatch(value):
            raise ValueError("event_name must use PascalCase without separators")
        if any(
            value.startswith(prefix) and len(value) > len(prefix) and value[len(prefix)].isupper()
            for prefix in _RESERVED_IMPERATIVE_PREFIXES
        ):
            raise ValueError("event_name must describe a completed fact, not a command")
        return value

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware UTC")
        if value.utcoffset() != timedelta(0):
            return value.astimezone(UTC)
        return value

    @field_validator("aggregate_type", "aggregate_id", "producer")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("event identity text fields must not be empty")
        return value

    @field_validator("payload", mode="before")
    @classmethod
    def normalize_payload(cls, value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="python")
        return dict(value)

    @classmethod
    def create(
        cls,
        *,
        event_name: str,
        event_version: int,
        correlation_id: str | None,
        aggregate_type: str,
        aggregate_id: str,
        producer: str,
        payload: Mapping[str, Any] | BaseModel,
        origin: EventOrigin,
        clock: EventClock | None = None,
        id_generator: EventIdGenerator | None = None,
        causation_id: str | None = None,
        severity: EventSeverity = EventSeverity.INFO,
        replay_id: str | None = None,
        replay_of_event_id: str | None = None,
    ) -> EventEnvelope:
        """Create an unpublished envelope using injected time and identity sources."""
        if clock is None or id_generator is None:
            raise ValueError("EventEnvelope.create requires injected clock and id_generator")
        return cls(
            event_id=id_generator.new_id(),
            event_name=event_name,
            event_version=event_version,
            occurred_at=clock.now(),
            correlation_id=correlation_id or id_generator.new_id(),
            causation_id=causation_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            producer=producer,
            severity=severity,
            payload=(
                payload.model_dump(mode="python")
                if isinstance(payload, BaseModel)
                else dict(payload)
            ),
            origin=origin,
            monotonic_ns=clock.monotonic_ns(),
            replay_id=replay_id,
            replay_of_event_id=replay_of_event_id,
        )

    def with_sequence(self, sequence: int) -> EventEnvelope:
        """Return a published copy with the sequencer-assigned sequence."""
        return self.model_copy(update={"sequence": sequence})

    def to_json_bytes(self) -> bytes:
        """Serialize the published envelope for exact append-only persistence."""
        return self.model_dump_json().encode("utf-8")


PayloadModel = TypeVar("PayloadModel", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class EventDefinition:
    """Catalog metadata and payload validator for one event schema version."""

    event_name: str
    event_version: int
    category: EventCategory
    payload_model: type[BaseModel]


class EventPayloadRegistry:
    """Registry keyed by the exact ``(event_name, event_version)`` pair."""

    def __init__(self) -> None:
        self._definitions: dict[tuple[str, int], EventDefinition] = {}

    def register(
        self,
        event_name: str,
        event_version: int,
        category: EventCategory,
        payload_model: type[BaseModel] = EventPayload,
    ) -> EventDefinition:
        key = (event_name, event_version)
        if key in self._definitions:
            raise ValueError(f"event schema already registered: {event_name} v{event_version}")
        if not _EVENT_NAME_RE.fullmatch(event_name):
            raise ValueError("event_name must use PascalCase without separators")
        if event_version < 1:
            raise ValueError("event_version must be positive")
        existing_categories = {
            definition.category
            for definition in self._definitions.values()
            if definition.event_name == event_name
        }
        if existing_categories and category not in existing_categories:
            raise ValueError(f"event {event_name} cannot change category between versions")
        definition = EventDefinition(
            event_name, event_version, EventCategory(category), payload_model
        )
        self._definitions[key] = definition
        return definition

    def definition(self, event_name: str, event_version: int) -> EventDefinition | None:
        """Return a known definition, or ``None`` for an explicit future pair."""
        return self._definitions.get((event_name, event_version))

    def category_for(self, event_name: str, event_version: int) -> EventCategory | None:
        definition = self.definition(event_name, event_version)
        return definition.category if definition else None

    def parse_payload(
        self,
        event_name: str,
        event_version: int,
        payload: Mapping[str, Any] | BaseModel,
    ) -> BaseModel:
        """Validate known payloads and preserve unknown pairs as opaque models."""
        definition = self.definition(event_name, event_version)
        if definition is None:
            return UnknownEventPayload.model_validate(payload)
        return definition.payload_model.model_validate(payload)

    def validate(self, event: EventEnvelope) -> BaseModel:
        """Validate a payload against its registered schema or explicit opaque fallback."""
        return self.parse_payload(event.event_name, event.event_version, event.payload)

    def definitions(self) -> tuple[EventDefinition, ...]:
        return tuple(
            sorted(
                self._definitions.values(), key=lambda item: (item.event_name, item.event_version)
            )
        )

    def catalog(self) -> dict[str, Any]:
        """Return the versioned, JSON-serializable catalog generated from registrations."""
        return {
            "catalog_version": EVENT_CATALOG_VERSION,
            "envelope": {
                "fields": list(EventEnvelope.model_fields),
                "schema": EventEnvelope.model_json_schema(),
                "unknown_fields": "preserved",
                "unknown_event_pairs": "accepted_as_opaque_payload",
                "client_asserted": {
                    "category": EventCategory.VIEWER.value,
                    "producer": "web-ui",
                },
                "replay_fields": ["replay_id", "replay_of_event_id"],
            },
            "events": [
                {
                    "event_name": definition.event_name,
                    "event_version": definition.event_version,
                    "category": definition.category.value,
                    "payload_model": f"{definition.payload_model.__module__}.{definition.payload_model.__name__}",
                    "payload_schema": definition.payload_model.model_json_schema(),
                    "origins": [origin.value for origin in EventOrigin],
                }
                for definition in self.definitions()
            ],
        }

    def catalog_json(self) -> bytes:
        return (json.dumps(self.catalog(), indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_default_event_registry() -> EventPayloadRegistry:
    """Build the initial catalog from the normative event taxonomy."""
    registry = EventPayloadRegistry()
    entries = {
        EventCategory.ASSOCIATION: (
            "AssociationStarted",
            "AssociationAccepted",
            "AssociationRejected",
            "AssociationReleased",
            "AssociationAborted",
        ),
        EventCategory.DIMSE: (
            "CEchoReceived",
            "CStoreReceived",
            "CFindReceived",
            "CFindCompleted",
            "CMoveRequested",
            "CGetRequested",
            "UnrecognizedDimseObserved",
        ),
        EventCategory.DATASET: (
            "DatasetLoaded",
            "DatasetParsed",
            "MetadataExtracted",
            "InstancePersisted",
        ),
        EventCategory.VIEWER: (
            "ImageDecoded",
            "ImageDisplayed",
            "WindowLevelChanged",
            "CineStarted",
        ),
        EventCategory.CAPTURE: (
            "CaptureStarted",
            "CaptureStopped",
            "CaptureCompleted",
            "CaptureInterrupted",
            "CapturePromoted",
        ),
        EventCategory.REPLAY: (
            "ReplayStarted",
            "ReplayPaused",
            "ReplayProgressed",
            "ReplayCompleted",
            "ReplayFinished",
        ),
        EventCategory.ANALYSIS: ("AnalysisCompleted",),
        EventCategory.REPORTING: ("ReportGenerated", "ReportExported"),
        EventCategory.PLUGIN: ("PluginLoaded",),
        EventCategory.SYSTEM: (
            "ApplicationStarted",
            "ApplicationStopped",
            "ErrorRaised",
            "WarningRaised",
            "EventsDropped",
            "ClockAnomalyDetected",
            "ConfigurationChanged",
        ),
    }
    for category, event_names in entries.items():
        for event_name in event_names:
            registry.register(event_name, 1, category)
    return registry


DEFAULT_EVENT_REGISTRY = build_default_event_registry()

__all__ = [
    "DEFAULT_EVENT_REGISTRY",
    "EVENT_CATALOG_VERSION",
    "EventCategory",
    "EventClock",
    "EventDefinition",
    "EventEnvelope",
    "EventIdGenerator",
    "EventOrigin",
    "EventPayload",
    "EventPayloadRegistry",
    "EventSeverity",
    "UnknownEventPayload",
    "build_default_event_registry",
]
