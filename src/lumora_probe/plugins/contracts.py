"""Stable DTOs exposed to trusted Lumora Probe plugins."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Literal, Protocol

PLUGIN_SDK_VERSION = "1.0"
PLUGIN_SDK_MAJOR = 1


class PluginHookName(StrEnum):
    """Hooks implemented by a plugin through the public SDK."""

    EVENTS = "on_event"
    ANALYZE = "analyze"
    REPORT = "contribute_report"
    COMMANDS = "register_commands"
    SETTINGS = "register_settings"


@dataclass(frozen=True, slots=True)
class EventDTO:
    """Immutable event projection; plugin code never receives an aggregate."""

    event_id: str
    event_name: str
    event_version: int
    sequence: int | None
    aggregate_type: str
    aggregate_id: str
    producer: str
    payload: Mapping[str, Any]
    origin: Literal["observed", "client-asserted"]

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.event_name.strip():
            raise ValueError("event_id and event_name must be non-empty")
        if self.event_version < 1:
            raise ValueError("event_version must be positive")
        if self.sequence is not None and self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if self.origin not in {"observed", "client-asserted"}:
            raise ValueError("origin must be observed or client-asserted")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True, slots=True)
class AnalysisContextDTO:
    """Observed evidence and conditions supplied to an analyzer hook."""

    events: tuple[EventDTO, ...]
    conditions: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class FindingDTO:
    """Finding returned by an analyzer without exposing the analysis aggregate."""

    rule_id: str
    rule_version: str
    rule_set_version: str
    confidence: Literal["certain", "likely", "possible"]
    cited_sequences: tuple[int, ...]
    explanation: str
    next_steps: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.rule_id.strip() or not self.rule_version.strip():
            raise ValueError("rule identity must be non-empty")
        if self.confidence not in {"certain", "likely", "possible"}:
            raise ValueError("confidence must be certain, likely, or possible")
        if tuple(sorted(set(self.cited_sequences))) != self.cited_sequences:
            raise ValueError("cited_sequences must be sorted and unique")
        if any(sequence < 0 for sequence in self.cited_sequences):
            raise ValueError("cited_sequences must be non-negative")
        if not self.explanation.strip() or not self.next_steps:
            raise ValueError("finding explanation and next_steps are required")


@dataclass(frozen=True, slots=True)
class ReportContextDTO:
    """Stable report inputs available to report-contributing plugins."""

    capture_id: str
    rule_set_version: str
    findings: tuple[FindingDTO, ...]


@dataclass(frozen=True, slots=True)
class ReportContributionDTO:
    """Named report section supplied by a plugin."""

    plugin_id: str
    title: str
    markdown: str


@dataclass(frozen=True, slots=True)
class CommandDTO:
    """CLI command metadata contributed by a plugin."""

    name: str
    summary: str
    handler_name: str


@dataclass(frozen=True, slots=True)
class SettingDTO:
    """Runtime setting metadata contributed by a plugin."""

    name: str
    description: str
    default: Any


@dataclass(frozen=True, slots=True)
class PluginDiagnostic:
    """Diagnostic emitted when a plugin fails or exceeds its budget."""

    event_name: Literal["ErrorRaised", "WarningRaised"]
    plugin_id: str
    hook: str
    message: str
    elapsed_ns: int | None = None
    budget_ns: int | None = None


@dataclass(frozen=True, slots=True)
class PluginHookObservation:
    """Timing fact emitted for every implemented hook, including successful calls."""

    plugin_id: str
    hook: str
    elapsed_ns: int
    failed: bool = False
    budget_breach: bool = False


class HookObservationSink(Protocol):
    """Application-owned observer for plugin timing metrics."""

    def __call__(self, observation: PluginHookObservation) -> None: ...


class DiagnosticSink(Protocol):
    """Application-owned sink for plugin diagnostics."""

    def __call__(self, diagnostic: PluginDiagnostic) -> None: ...


__all__: tuple[str, ...] = ()
