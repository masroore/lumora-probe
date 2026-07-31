"""Production composition root for the Phase 17 observable application."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from fastapi import FastAPI

from lumora_probe.core.alerts import AlertRegistry, AlertThresholds
from lumora_probe.core.audit import AuditCategory, AuditLog
from lumora_probe.core.bus import EventBus
from lumora_probe.core.clock import SystemClock
from lumora_probe.core.config import StartupConfig
from lumora_probe.core.health import HealthRegistry
from lumora_probe.core.lifecycle import ServiceHealth
from lumora_probe.core.logging import get_logger, log_operational
from lumora_probe.core.metrics import MetricRegistry
from lumora_probe.core.paths import DataPaths
from lumora_probe.core.storage import StorageDatabases
from lumora_probe.plugins.contracts import PluginDiagnostic
from lumora_probe.plugins.repository import PluginRepository
from lumora_probe.plugins.service import PluginService
from lumora_probe.web.api import create_app
from lumora_probe.web.live import LiveEventSource
from lumora_probe.web.security import SecurityPolicy
from lumora_probe.web.settings_routes import InMemorySettingsProvider


class PluginServiceAdapter:
    """Adapt domain records to the web mapping contract at the composition root."""

    def __init__(
        self,
        service: PluginService,
        *,
        audit: AuditLog,
        clock: SystemClock,
        metrics: MetricRegistry | None = None,
    ) -> None:
        self.service = service
        self.audit = audit
        self.clock = clock
        self.metrics = metrics

    def records(self) -> Sequence[Mapping[str, Any]]:
        return tuple(record.as_dict() for record in self.service.records())

    def inspect(self, plugin_id: str) -> Mapping[str, Any]:
        return self.service.inspect(plugin_id).as_dict()

    async def set_enabled(self, plugin_id: str, enabled: bool) -> Mapping[str, Any]:
        record = self.service.set_enabled(plugin_id, enabled)
        if self.metrics is not None:
            self.metrics.set_plugin_status(plugin_id, record.status.value)
        await self.audit.append(
            AuditCategory.ADMINISTRATIVE_ACTION,
            entity_type="plugin",
            entity_id=plugin_id,
            occurred_at=self.clock.now(),
            payload={"action": "enable" if enabled else "disable", "plugin": record.as_dict()},
        )
        return record.as_dict()


class HealthRegistryAdapter:
    """Convert core health value objects to the web provider mapping shape."""

    def __init__(self, registry: HealthRegistry) -> None:
        self.registry = registry

    async def check(self) -> Mapping[str, object]:
        return (await self.registry.check()).as_dict()


class AuditedSettingsProvider:
    """Persist runtime setting mutations in the existing application audit log."""

    def __init__(self, audit: AuditLog, clock: SystemClock) -> None:
        self._inner = InMemorySettingsProvider()
        self._audit = audit
        self._clock = clock

    async def get(self) -> Mapping[str, Any]:
        return await self._inner.get()

    async def update(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        result = await self._inner.update(values)
        await self._audit.append(
            AuditCategory.CONFIGURATION_CHANGE,
            entity_type="runtime-settings",
            occurred_at=self._clock.now(),
            payload={"keys": sorted(values)},
        )
        return result


def build_production_app(config: StartupConfig) -> FastAPI:
    """Create the fully composed app using the canonical data root and production services."""
    paths = DataPaths.from_config(config)
    paths.initialise()
    clock = SystemClock()
    storage = StorageDatabases.from_paths(paths)
    storage.initialise()
    audit = AuditLog(storage.app)
    bus = EventBus(clock=clock)
    metrics = MetricRegistry()
    alerts = AlertRegistry(metrics, _thresholds(config))
    health = HealthRegistry()
    plugin_repo = PluginRepository(paths.plugins)

    def diagnostic_sink(diagnostic: PluginDiagnostic) -> None:
        metrics.observe_plugin_diagnostic(diagnostic)
        log_operational(
            get_logger("lumora.plugins"),
            "plugin hook diagnostic",
            level="warning",
            plugin_id=diagnostic.plugin_id,
            hook=diagnostic.hook,
            diagnostic=diagnostic.event_name,
            diagnostic_message=diagnostic.message,
            elapsed_ns=diagnostic.elapsed_ns,
            budget_ns=diagnostic.budget_ns,
        )

    plugin_service = PluginService(
        plugin_repo,
        clock=clock,
        diagnostic_sink=diagnostic_sink,
        timing_sink=metrics.observe_plugin_timing,
    )
    plugin_provider = PluginServiceAdapter(
        plugin_service, audit=audit, clock=clock, metrics=metrics
    )
    for record in plugin_service.records():
        metrics.set_plugin_status(record.manifest.plugin_id, record.status.value)

    health.register(
        "event-bus",
        lambda: ServiceHealth("event-bus", bus.started, True, None if bus.started else "stopped"),
    )
    health.register("index-db", lambda: _database_health("index-db", storage.index.path))
    health.register("app-db", lambda: _database_health("app-db", storage.app.path))
    health.register("plugin-host", lambda: _plugin_health(plugin_service))

    async def security_audit_sink(code: str, payload: Mapping[str, object]) -> None:
        await audit.append(
            AuditCategory.SECURITY_FAILURE,
            entity_type="http-request",
            occurred_at=clock.now(),
            payload={"code": code, **dict(payload)},
        )

    application = create_app(
        clock=clock,
        event_clock=clock,
        event_bus=cast(LiveEventSource, bus),
        event_id_generator=bus.id_generator,
        health_provider=HealthRegistryAdapter(health),
        metrics_provider=metrics,
        alert_provider=alerts,
        audit_provider=audit,
        security_audit_sink=security_audit_sink,
        settings_provider=AuditedSettingsProvider(audit, clock),
        plugin_provider=plugin_provider,
        security_policy=SecurityPolicy(read_only=config.read_only),
    )
    application.state.config = config
    application.state.paths = paths
    application.state.storage = storage
    application.state.event_bus = bus
    application.state.health_registry = health
    application.state.metrics = metrics
    application.state.alerts = alerts
    application.state.audit_log = audit
    application.state.plugin_service = plugin_service
    application.state.plugin_provider = plugin_provider
    return application


def _database_health(name: str, path: Any) -> ServiceHealth:
    ready = path.is_file()
    return ServiceHealth(name, ready, True, None if ready else f"missing database: {path}")


def _plugin_health(service: PluginService) -> ServiceHealth:
    result = service.health()
    return ServiceHealth(result.name, result.ready, result.alive, result.detail)


def _thresholds(config: StartupConfig) -> AlertThresholds:
    return AlertThresholds(
        plugin_errors_warning=getattr(config, "plugin_errors_warning", 1),
        plugin_errors_critical=getattr(config, "plugin_errors_critical", 3),
        budget_breaches_warning=getattr(config, "budget_breaches_warning", 1),
        budget_breaches_critical=getattr(config, "budget_breaches_critical", 3),
        event_drops_warning=getattr(config, "event_drops_warning", 1),
        event_drops_critical=getattr(config, "event_drops_critical", 10),
    )


__all__ = ["HealthRegistryAdapter", "PluginServiceAdapter", "build_production_app"]
