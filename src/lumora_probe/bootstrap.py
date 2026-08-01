"""Production composition root for the Phase 17 observable application."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI

from lumora_probe.associations.network import DICOMListener, DICOMListenerConfig
from lumora_probe.captures.repository import CaptureRepository
from lumora_probe.captures.service import CaptureEngine
from lumora_probe.core.alerts import AlertRegistry, AlertThresholds
from lumora_probe.core.audit import AuditCategory, AuditLog
from lumora_probe.core.bus import EventBus
from lumora_probe.core.clock import SystemClock
from lumora_probe.core.config import StartupConfig
from lumora_probe.core.health import HealthRegistry
from lumora_probe.core.lifecycle import LifecycleManager, ServiceHealth
from lumora_probe.core.logging import get_logger, log_operational
from lumora_probe.core.metrics import MetricRegistry
from lumora_probe.core.paths import DataPaths
from lumora_probe.core.storage import StorageDatabases
from lumora_probe.plugins.contracts import PluginDiagnostic
from lumora_probe.plugins.repository import PluginRepository
from lumora_probe.plugins.service import PluginService
from lumora_probe.settings.runtime import RuntimeSettingsStore
from lumora_probe.web.api import create_app
from lumora_probe.web.live import LiveEventSource
from lumora_probe.web.security import SecurityPolicy


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
    """Adapt the persistent runtime settings store to the HTTP provider contract."""

    def __init__(self, store: RuntimeSettingsStore, audit: AuditLog, clock: SystemClock) -> None:
        self._store = store
        self._audit = audit
        self._clock = clock

    async def get(self) -> Mapping[str, Any]:
        return {
            "items": [
                {"name": snapshot.name, "value": snapshot.value, "source": snapshot.source}
                for snapshot in self._store.snapshots()
            ]
        }

    async def update(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        changed = []
        for name, value in values.items():
            snapshot = self._store.update(name, value)
            changed.append(
                {"name": snapshot.name, "value": snapshot.value, "source": snapshot.source}
            )
        await self._audit.append(
            AuditCategory.CONFIGURATION_CHANGE,
            entity_type="runtime-settings",
            occurred_at=self._clock.now(),
            payload={"keys": sorted(values)},
        )
        return {"items": changed}


class _CaptureEngineAdapter:
    """Present CaptureEngine as a lifecycle.Service, closing over the event bus."""

    name = "capture-engine"

    def __init__(self, engine: Any, *, event_bus: Any | None) -> None:
        self._engine = engine
        self._bus = event_bus

    async def start(self) -> None:
        await self._engine.start(event_bus=self._bus)

    async def stop(self) -> None:
        await self._engine.stop()

    async def stop_accepting(self) -> None:
        await self._engine.stop_accepting()

    async def drain(self) -> None:
        await self._engine.drain()

    async def flush(self) -> None:
        await self._engine.flush()

    async def interrupt(self, reason: str = "shutdown deadline") -> None:
        await self._engine.interrupt(reason)

    def health(self) -> ServiceHealth:
        return self._engine.health()


class _IndexRecoveryAdapter:
    name = "index-recovery"

    def __init__(
        self, repository: CaptureRepository, paths: DataPaths, config: StartupConfig
    ) -> None:
        self.repository = repository
        self.paths = paths
        self.config = config
        self.recovered = False
        self.error: str | None = None

    async def start(self) -> None:
        try:
            await self.repository.rebuild(
                self.paths.captures, additional_roots=self.paths.additional_capture_roots
            )
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            raise
        self.recovered = True

    async def stop(self) -> None:
        return None

    def health(self) -> ServiceHealth:
        return ServiceHealth(
            self.name,
            self.recovered,
            self.error is None,
            self.error or (None if self.recovered else "recovery pending"),
        )


class _CaptureResourceStore:
    def __init__(self, repository: CaptureRepository) -> None:
        self.repository = repository

    async def list(self, resource: str) -> tuple[Mapping[str, Any], ...]:
        if resource != "captures":
            return ()
        records = await self.repository.list_captures()
        return tuple(_capture_mapping(record) for record in records)

    async def get(self, resource: str, resource_id: str) -> Mapping[str, Any] | None:
        for record in await self.list(resource):
            if record.get("capture_id") == resource_id:
                return record
        return None

    async def delete(self, resource: str, resource_id: str) -> bool:
        record = await self.get(resource, resource_id)
        if record is None:
            return False
        path = Path(str(record["path"])).resolve()
        allowed = tuple(
            self.repository.databases.index.path.parent / "captures",
        )
        if not any(path.parent == root.resolve() for root in allowed):
            raise ValueError("capture is outside the primary capture root")
        import shutil

        shutil.rmtree(path)
        await self.repository.remove_index_entry(resource_id)
        return True


def _capture_mapping(record: Any) -> Mapping[str, Any]:
    return {
        "capture_id": record.capture_id,
        "path": record.path,
        "source_root": record.source_root,
        "format_version": record.format_version,
        "created_at": record.created_at.isoformat(),
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
        "state": record.state,
        "fidelity": record.fidelity,
        "partial": record.partial,
        "promoted_from_buffer": record.promoted_from_buffer,
        "interruption_reason": record.interruption_reason,
        "manifest_sha256": record.manifest_sha256,
        "indexed_at": record.indexed_at.isoformat(),
        "objects": [
            item.__dict__
            if hasattr(item, "__dict__")
            else {
                "digest": item.digest,
                "study_uid": item.study_uid,
                "series_uid": item.series_uid,
                "sop_instance_uid": item.sop_instance_uid,
                "size": item.size,
            }
            for item in record.objects
        ],
    }


class _EventBusAdapter:
    name = "event-bus"

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus

    async def start(self) -> None:
        await self.bus.start()

    async def stop(self) -> None:
        await self.bus.stop()

    def health(self) -> ServiceHealth:
        return ServiceHealth(
            self.name, self.bus.started, self.bus.started, None if self.bus.started else "stopped"
        )


def _not_started_alive(health: ServiceHealth) -> ServiceHealth:
    return ServiceHealth(health.name, health.ready, True, health.detail)


def _listener_health(listener: DICOMListener) -> ServiceHealth:
    return ServiceHealth(
        listener.name,
        listener.started,
        listener.started,
        None if listener.started else "listener stopped",
    )


def _default_allowed_hosts(config: StartupConfig) -> tuple[str, ...]:
    hosts = {"localhost", "127.0.0.1", "[::1]"}
    if config.bind_host not in {"0.0.0.0", "::"}:
        hosts.add(config.bind_host)
    return tuple(sorted(hosts))


def build_production_app(config: StartupConfig) -> FastAPI:
    """Create the fully composed app using the canonical data root and production services."""
    paths = DataPaths.from_config(config)
    paths.initialise()
    clock = SystemClock()
    storage = StorageDatabases.from_paths(paths)
    storage.app.initialise()
    storage.index.initialise()
    audit = AuditLog(storage.app)
    bus = EventBus(clock=clock)
    lifecycle = LifecycleManager(shutdown_grace_seconds=config.shutdown_grace_seconds)
    capture_repository = CaptureRepository(storage, clock=clock)
    recovery = _IndexRecoveryAdapter(capture_repository, paths, config)
    capture_engine = CaptureEngine(
        paths.captures,
        ring_root=paths.ringbuffer,
        event_ingress=bus,
        capture_repository=capture_repository,
        clock=clock,
        id_generator=bus.id_generator,
    )
    lifecycle.register(_EventBusAdapter(bus))
    lifecycle.register(recovery)
    lifecycle.register(_CaptureEngineAdapter(capture_engine, event_bus=bus))
    dicom_listener = DICOMListener(
        DICOMListenerConfig(bind_host=config.dicom_bind_host, port=config.dicom_port),
        event_ingress=bus,
        c_store_sink=capture_engine.store_c_store,
        pdu_trace_sink=capture_engine,
        clock=clock,
        id_generator=bus.id_generator,
    )
    lifecycle.register(dicom_listener)
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
    health.register("index-recovery", recovery.health)
    health.register("index-db", lambda: _database_health("index-db", storage.index.path))
    health.register("capture-engine", lambda: _not_started_alive(capture_engine.health()))
    health.register("dicom-listener", lambda: _not_started_alive(_listener_health(dicom_listener)))
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
        capture_engine=capture_engine,
        capture_store=_CaptureResourceStore(capture_repository),
        lifecycle_manager=lifecycle,
        event_id_generator=bus.id_generator,
        health_provider=HealthRegistryAdapter(health),
        metrics_provider=metrics,
        alert_provider=alerts,
        audit_provider=audit,
        security_audit_sink=security_audit_sink,
        settings_provider=AuditedSettingsProvider(
            RuntimeSettingsStore(
                paths.settings_file, event_publisher=bus, clock=clock, id_generator=bus.id_generator
            ),
            audit,
            clock,
        ),
        plugin_provider=plugin_provider,
        security_policy=SecurityPolicy(
            read_only=config.read_only,
            allowed_hosts=config.allowed_hosts or _default_allowed_hosts(config),
            allowed_origins=config.allowed_origins,
            trusted_proxies=config.trusted_proxies,
        ),
    )
    application.state.config = config
    application.state.paths = paths
    application.state.storage = storage
    application.state.event_bus = bus
    application.state.lifecycle_manager = lifecycle
    application.state.health_registry = health
    application.state.metrics = metrics
    application.state.alerts = alerts
    application.state.audit_log = audit
    application.state.plugin_service = plugin_service
    application.state.plugin_provider = plugin_provider
    application.state.dicom_listener = dicom_listener
    application.state.executor_workers = config.executor_workers
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
