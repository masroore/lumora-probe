"""Configurable in-process alert thresholds over event-derived metrics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .metrics import MetricRegistry


class AlertState(StrEnum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class AlertThresholds:
    """Thresholds for the high-signal operational conditions."""

    plugin_errors_warning: int = 1
    plugin_errors_critical: int = 3
    budget_breaches_warning: int = 1
    budget_breaches_critical: int = 3
    event_drops_warning: int = 1
    event_drops_critical: int = 10
    hysteresis_ratio: float = 0.8

    def __post_init__(self) -> None:
        for name in (
            "plugin_errors_warning",
            "plugin_errors_critical",
            "budget_breaches_warning",
            "budget_breaches_critical",
            "event_drops_warning",
            "event_drops_critical",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must not be negative")
        if not 0 < self.hysteresis_ratio < 1:
            raise ValueError("hysteresis_ratio must be between zero and one")


@dataclass(frozen=True, slots=True)
class Alert:
    name: str
    state: AlertState
    value: float
    threshold: float
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "value": self.value,
            "threshold": self.threshold,
            "detail": self.detail,
        }


class AlertRegistry:
    """Evaluate alert facts from the metric projection; no independent counters."""

    def __init__(self, metrics: MetricRegistry, thresholds: AlertThresholds | None = None) -> None:
        self.metrics = metrics
        self.thresholds = thresholds or AlertThresholds()
        self._states: dict[str, AlertState] = {}

    def snapshot(self) -> tuple[Alert, ...]:
        values = {(item.name, item.labels): item.value for item in self.metrics.snapshot()}
        checks = (
            (
                "plugin_errors",
                "plugin.hook.errors",
                self.thresholds.plugin_errors_warning,
                self.thresholds.plugin_errors_critical,
            ),
            (
                "plugin_budget_breaches",
                "plugin.hook.budget_breaches",
                self.thresholds.budget_breaches_warning,
                self.thresholds.budget_breaches_critical,
            ),
            (
                "event_drops",
                "events.dropped",
                self.thresholds.event_drops_warning,
                self.thresholds.event_drops_critical,
            ),
        )
        alerts: list[Alert] = []
        for name, metric_name, warning, critical in checks:
            value = sum(
                value for (metric, _labels), value in values.items() if metric == metric_name
            )
            previous = self._states.get(name, AlertState.OK)
            if (
                previous is AlertState.CRITICAL
                and value >= critical * self.thresholds.hysteresis_ratio
            ):
                state = AlertState.CRITICAL
            elif (
                previous is AlertState.WARNING
                and value >= warning * self.thresholds.hysteresis_ratio
            ):
                state = AlertState.WARNING
            elif value >= critical and critical:
                state = AlertState.CRITICAL
            elif value >= warning and warning:
                state = AlertState.WARNING
            else:
                state = AlertState.OK
            self._states[name] = state
            threshold = critical if state is AlertState.CRITICAL else warning
            alerts.append(Alert(name, state, value, threshold, f"{metric_name}={value:g}"))
        return tuple(alerts)

    def as_dict(self) -> dict[str, Any]:
        return {"items": [alert.as_dict() for alert in self.snapshot()]}


__all__ = ["Alert", "AlertRegistry", "AlertState", "AlertThresholds"]
