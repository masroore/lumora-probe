# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Plugin discovery, validation, loading, and hook containment."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from typing import Any, Protocol

from .api import build_plugin_manager
from .contracts import (
    PLUGIN_SDK_MAJOR,
    AnalysisContextDTO,
    CommandDTO,
    DiagnosticSink,
    EventDTO,
    FindingDTO,
    HookObservationSink,
    PluginDiagnostic,
    PluginHookName,
    PluginHookObservation,
    ReportContextDTO,
    ReportContributionDTO,
    SettingDTO,
)
from .domain import PluginHealth, PluginManifest, PluginPolicy, PluginRecord, PluginStatus
from .repository import PluginRepository


class PluginObject(Protocol):
    """Minimum structural shape of a loaded plugin object."""


class MonotonicClock(Protocol):
    """Host-injected monotonic source; production wiring supplies ``core.Clock``."""

    def monotonic_ns(self) -> int: ...


HookInput = EventDTO | AnalysisContextDTO | ReportContextDTO | None
HookOutput = Any


class PluginService:
    """Manage trusted in-process plugins with explicit failure containment."""

    def __init__(
        self,
        repository: PluginRepository,
        *,
        policy: PluginPolicy | None = None,
        clock: MonotonicClock | None = None,
        diagnostic_sink: DiagnosticSink | None = None,
        timing_sink: HookObservationSink | None = None,
    ) -> None:
        self.repository = repository
        self.policy = policy or PluginPolicy()
        self.clock = clock
        self.diagnostic_sink = diagnostic_sink
        self.timing_sink = timing_sink
        self._manager = build_plugin_manager()
        self._plugins: dict[str, Any] = {}
        self._records: dict[str, PluginRecord] = {}
        self.load_enabled()

    def load_enabled(self) -> tuple[PluginRecord, ...]:
        """Load only explicitly enabled plugins; invalid plugins remain isolated."""

        self._manager = build_plugin_manager()
        self._plugins.clear()
        self._records.clear()
        for manifest in self.repository.discover():
            if not self.repository.is_enabled(manifest.plugin_id):
                self._records[manifest.plugin_id] = PluginRecord(
                    manifest=manifest, status=PluginStatus.DISABLED
                )
                continue
            self._load_one(manifest)
        return self.records()

    def records(self) -> tuple[PluginRecord, ...]:
        """Return deterministic plugin health and trust metadata."""

        return tuple(self._records[key] for key in sorted(self._records))

    def health(self) -> PluginHealth:
        """Return aggregate plugin-host health and name failing plugins."""
        records = self.records()
        unhealthy = tuple(
            record.manifest.plugin_id for record in records if record.health_state == "unhealthy"
        )
        degraded = tuple(
            record.manifest.plugin_id for record in records if record.health_state == "degraded"
        )
        ready = not unhealthy
        detail = None
        if unhealthy:
            detail = f"unhealthy plugins: {', '.join(unhealthy)}"
        elif degraded:
            detail = f"degraded plugins: {', '.join(degraded)}"
        return PluginHealth("plugin-host", ready, True, detail)

    def inspect(self, plugin_id: str) -> PluginRecord:
        """Return one plugin record."""

        try:
            return self._records[plugin_id]
        except KeyError as error:
            raise KeyError(f"unknown plugin: {plugin_id}") from error

    def set_enabled(self, plugin_id: str, enabled: bool) -> PluginRecord:
        """Persist restart-scoped enablement without executing plugin code."""

        manifest = self.repository.set_enabled(plugin_id, enabled)
        record = PluginRecord(
            manifest=manifest,
            status=PluginStatus.ENABLED if enabled else PluginStatus.DISABLED,
        )
        self._records[plugin_id] = record
        if not enabled:
            self._plugins.pop(plugin_id, None)
        return record

    def install_check(self, source: Path) -> PluginManifest:
        """Validate a deliberately placed plugin directory without installing it."""

        return self.repository.install_directory(source)

    def run_event(self, event: EventDTO) -> None:
        """Dispatch one event to enabled plugins with containment."""

        self._run_hook(PluginHookName.EVENTS, event)

    def analyze(self, context: AnalysisContextDTO) -> tuple[FindingDTO, ...]:
        """Collect analyzer findings while isolating each plugin."""

        return self._collect(PluginHookName.ANALYZE, context)

    def contribute_report(self, context: ReportContextDTO) -> tuple[ReportContributionDTO, ...]:
        """Collect report sections while isolating each plugin."""

        return self._collect(PluginHookName.REPORT, context)

    def commands(self) -> tuple[CommandDTO, ...]:
        """Collect command metadata from enabled plugins."""

        return self._collect(PluginHookName.COMMANDS, None)

    def settings(self) -> tuple[SettingDTO, ...]:
        """Collect setting metadata from enabled plugins."""

        return self._collect(PluginHookName.SETTINGS, None)

    def _load_one(self, manifest: PluginManifest) -> None:
        if not (manifest.sdk_min <= PLUGIN_SDK_MAJOR <= manifest.sdk_max):
            self._records[manifest.plugin_id] = PluginRecord(
                manifest=manifest,
                status=PluginStatus.INVALID,
                last_error="plugin SDK major is incompatible with this application",
            )
            return
        try:
            plugin = self._import_entry_point(manifest)
            for hook in manifest.hooks:
                implementation = getattr(plugin, hook.value, None)
                if not callable(implementation):
                    raise TypeError(f"declared hook {hook.value!r} is not implemented")
            self._manager.register(plugin, name=manifest.plugin_id)
            self._plugins[manifest.plugin_id] = plugin
            self._records[manifest.plugin_id] = PluginRecord(
                manifest=manifest, status=PluginStatus.LOADED
            )
        except Exception as error:  # noqa: BLE001 - plugin code is an isolation boundary
            self._records[manifest.plugin_id] = PluginRecord(
                manifest=manifest,
                status=PluginStatus.INVALID,
                last_error=str(error),
            )

    def _import_entry_point(self, manifest: PluginManifest) -> Any:
        module_name, separator, attribute = manifest.entry_point.partition(":")
        if not separator or not module_name or not attribute:
            raise ValueError("entry_point must use module:attribute syntax")
        source_path = manifest.path / f"{module_name}.py"
        if source_path.is_file():
            qualified_name = f"lumora_plugin_{manifest.plugin_id.replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(qualified_name, source_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load plugin module {source_path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            module = importlib.import_module(module_name)
        plugin = getattr(module, attribute, None)
        if plugin is None:
            raise AttributeError(f"plugin entry point attribute not found: {attribute}")
        return plugin() if isinstance(plugin, type) else plugin

    def _collect(self, hook: PluginHookName, value: HookInput) -> tuple[Any, ...]:
        collected: list[Any] = []
        for plugin_id in tuple(sorted(self._plugins)):
            result = self._run_hook(hook, value, plugin_id=plugin_id)
            if result is None:
                continue
            try:
                collected.extend(result)
            except TypeError as error:
                self._fail(plugin_id, hook, error, elapsed_ns=None)
        return tuple(collected)

    def _run_hook(
        self,
        hook: PluginHookName,
        value: HookInput,
        *,
        plugin_id: str | None = None,
    ) -> HookOutput:
        ids = (plugin_id,) if plugin_id is not None else tuple(sorted(self._plugins))
        result: HookOutput = None
        for current_id in ids:
            plugin = self._plugins.get(current_id)
            if plugin is None:
                continue
            implementation = getattr(plugin, hook.value, None)
            if implementation is None:
                continue
            start = self.clock.monotonic_ns() if self.clock is not None else 0
            try:
                result = implementation(value) if value is not None else implementation()
                if hook in {PluginHookName.ANALYZE, PluginHookName.REPORT}:
                    result = tuple(result or ())
                end = self.clock.monotonic_ns() if self.clock is not None else start
                elapsed_ns = end - start
            except Exception as error:  # noqa: BLE001 - plugin code is an isolation boundary
                end = self.clock.monotonic_ns() if self.clock is not None else start
                if self.timing_sink is not None:
                    self.timing_sink(
                        PluginHookObservation(current_id, hook.value, end - start, failed=True)
                    )
                self._fail(current_id, hook, error, elapsed_ns=end - start)
                continue
            if elapsed_ns > self.policy.hook_budget_ns:
                if self.timing_sink is not None:
                    self.timing_sink(
                        PluginHookObservation(
                            current_id, hook.value, elapsed_ns, budget_breach=True
                        )
                    )
                self._fail(
                    current_id,
                    hook,
                    RuntimeError("plugin hook exceeded its time budget"),
                    elapsed_ns=elapsed_ns,
                    budget_breach=True,
                )
            else:
                if self.timing_sink is not None:
                    self.timing_sink(PluginHookObservation(current_id, hook.value, elapsed_ns))
                self._update_record(current_id, last_elapsed_ns=elapsed_ns)
            if plugin_id is not None:
                return result
        return result

    def _fail(
        self,
        plugin_id: str,
        hook: PluginHookName,
        error: Exception,
        *,
        elapsed_ns: int | None,
        budget_breach: bool = False,
    ) -> None:
        current = self._records[plugin_id]
        failures = current.failure_count + 1
        event_name = "WarningRaised" if budget_breach else "ErrorRaised"
        message = str(error)
        if budget_breach:
            message = f"plugin hook exceeded budget: {message}"
        self._update_record(
            plugin_id,
            status=PluginStatus.FAILED
            if failures >= self.policy.max_failures
            else PluginStatus.LOADED,
            failure_count=failures,
            last_error=message,
            last_elapsed_ns=elapsed_ns,
        )
        if self.diagnostic_sink is not None:
            self.diagnostic_sink(
                PluginDiagnostic(
                    event_name=event_name,
                    plugin_id=plugin_id,
                    hook=hook.value,
                    message=message,
                    elapsed_ns=elapsed_ns,
                    budget_ns=self.policy.hook_budget_ns if budget_breach else None,
                )
            )
        if failures >= self.policy.max_failures:
            self._plugins.pop(plugin_id, None)
            self.repository.set_enabled(plugin_id, False)

    def _update_record(self, plugin_id: str, **changes: Any) -> None:
        current = self._records[plugin_id]
        self._records[plugin_id] = PluginRecord(
            manifest=current.manifest,
            status=changes.get("status", current.status),
            failure_count=changes.get("failure_count", current.failure_count),
            last_error=changes.get("last_error", current.last_error),
            last_elapsed_ns=changes.get("last_elapsed_ns", current.last_elapsed_ns),
        )


__all__: tuple[str, ...] = ()
