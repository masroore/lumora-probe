# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Event-derived operational metrics with one projection path."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from lumora_probe.shared.events import EventEnvelope


class PluginDiagnosticLike(Protocol):
    """Structural diagnostic contract so core never imports the plugin slice."""

    @property
    def event_name(self) -> str: ...

    @property
    def plugin_id(self) -> str: ...

    @property
    def hook(self) -> str: ...

    @property
    def elapsed_ns(self) -> int | None: ...

    @property
    def budget_ns(self) -> int | None: ...


class PluginHookObservationLike(Protocol):
    """Structural timing contract so core never imports the plugin slice."""

    @property
    def plugin_id(self) -> str: ...

    @property
    def hook(self) -> str: ...

    @property
    def elapsed_ns(self) -> int: ...


class MetricKind(StrEnum):
    """The supported in-process metric shapes."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass(frozen=True, slots=True)
class MetricValue:
    """A serializable metric sample."""

    name: str
    value: float
    labels: tuple[tuple[str, str], ...]
    kind: MetricKind
    count: int | None = None
    minimum: float | None = None
    maximum: float | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "value": self.value,
            "labels": dict(self.labels),
            "kind": self.kind.value,
        }
        if self.count is not None:
            result["count"] = self.count
        if self.minimum is not None:
            result["minimum"] = self.minimum
        if self.maximum is not None:
            result["maximum"] = self.maximum
        return result


@dataclass(slots=True)
class _Histogram:
    count: int = 0
    total: float = 0.0
    minimum: float | None = None
    maximum: float | None = None

    def observe(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)


class MetricRegistry:
    """Project every accepted event into metrics without a second domain counter API."""

    def __init__(self) -> None:
        self._counters: defaultdict[tuple[str, tuple[tuple[str, str], ...]], int] = defaultdict(int)
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._histograms: dict[tuple[str, tuple[tuple[str, str], ...]], _Histogram] = {}
        self._subscription: Any | None = None

    async def attach(self, bus: Any) -> None:
        """Subscribe to the loop-owned event bus exactly once."""
        if self._subscription is None:
            self._subscription = await bus.subscribe(self.observe, channel="capture")

    async def detach(self) -> None:
        if self._subscription is not None:
            await self._subscription.close()
            self._subscription = None

    def observe(self, event: EventEnvelope) -> None:
        """Record one accepted envelope. This is the only domain activity write path."""
        self._counter("events.total")
        self._counter("events.by_name", event_name=event.event_name)
        self._counter("events.by_category", category=event_category(event))
        self._counter("events.by_severity", severity=event.severity.value)
        self._counter(f"events.category.{event_category(event).lower()}")

        if event.event_name == "EventsDropped":
            dropped = _number(event.payload.get("dropped_count"), default=1)
            self._counter("events.dropped", amount=dropped)
        if event.event_name in {"ErrorRaised", "WarningRaised"}:
            source = str(event.payload.get("source", event.producer))
            self._counter("diagnostics.total", severity=event.severity.value, source=source)
        if event.event_name.startswith("Association"):
            self._counter("dicom.associations", event_name=event.event_name)
        if event.event_name.startswith("Replay"):
            self._counter("replay.events", event_name=event.event_name)
        if event.event_name.startswith("Capture"):
            self._counter("capture.events", event_name=event.event_name)

    def observe_plugin_diagnostic(self, diagnostic: PluginDiagnosticLike) -> None:
        """Project plugin failures and timings using the same metric registry."""
        labels = {"plugin_id": diagnostic.plugin_id, "hook": diagnostic.hook}
        if diagnostic.event_name == "ErrorRaised":
            self._counter("plugin.hook.errors", **labels)

    def observe_plugin_timing(self, observation: PluginHookObservationLike) -> None:
        """Record invocation timing; diagnostic callbacks own failure counters."""
        labels = {"plugin_id": observation.plugin_id, "hook": observation.hook}
        self._counter("plugin.hook.invocations", **labels)
        self._histogram("plugin.hook.elapsed_ns", observation.elapsed_ns, **labels)
        if getattr(observation, "budget_breach", False):
            self._counter("plugin.hook.budget_breaches", plugin_id=observation.plugin_id)

    def set_plugin_status(self, plugin_id: str, status: str) -> None:
        """Set a diagnostic gauge for a discovered plugin."""
        self._gauge("plugin.status", _status_value(status), plugin_id=plugin_id, status=status)

    def snapshot(self) -> tuple[MetricValue, ...]:
        values: list[MetricValue] = []
        for (name, labels), value in self._counters.items():
            values.append(MetricValue(name, float(value), labels, MetricKind.COUNTER))
        for (name, labels), value in self._gauges.items():
            values.append(MetricValue(name, value, labels, MetricKind.GAUGE))
        for (name, labels), histogram in self._histograms.items():
            values.append(
                MetricValue(
                    name,
                    histogram.total,
                    labels,
                    MetricKind.HISTOGRAM,
                    count=histogram.count,
                    minimum=histogram.minimum,
                    maximum=histogram.maximum,
                )
            )
        return tuple(sorted(values, key=lambda item: (item.name, item.labels, item.kind.value)))

    def snapshot_dict(self) -> dict[str, Any]:
        return {"items": [value.as_dict() for value in self.snapshot()]}

    def plugin_snapshot(self) -> dict[str, Any]:
        return {
            "items": [
                value.as_dict()
                for value in self.snapshot()
                if any(key == "plugin_id" for key, _ in value.labels)
            ]
        }

    def _counter(self, name: str, **labels: str | float) -> None:
        key = (name, _labels(labels))
        self._counters[key] += 1 if name != "events.dropped" else int(labels.pop("amount", 1))

    def _gauge(self, name: str, value: float, **labels: str) -> None:
        self._gauges[(name, _labels(labels))] = value

    def _histogram(self, name: str, value: float, **labels: str) -> None:
        key = (name, _labels(labels))
        self._histograms.setdefault(key, _Histogram()).observe(value)


def event_category(event: EventEnvelope) -> str:
    """Return catalog category without making metrics depend on event internals."""
    from lumora_probe.shared.events import DEFAULT_EVENT_REGISTRY

    category = DEFAULT_EVENT_REGISTRY.category_for(event.event_name, event.event_version)
    return category.value if category is not None else "Unknown"


def _labels(labels: Mapping[str, str | int | float]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((key, str(value)) for key, value in labels.items() if key != "amount"))


def _number(value: object, *, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _status_value(status: str) -> float:
    return {"loaded": 1.0, "enabled": 1.0, "failed": 0.0, "invalid": 0.0}.get(status, 0.0)


__all__ = ["MetricKind", "MetricRegistry", "MetricValue", "event_category"]
