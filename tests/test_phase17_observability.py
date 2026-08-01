# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Phase 17 observability acceptance coverage."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from lumora_probe.bootstrap import build_production_app
from lumora_probe.core.alerts import AlertRegistry, AlertState, AlertThresholds
from lumora_probe.core.audit import AUDIT_CATEGORY_COVERAGE, AuditCategory
from lumora_probe.core.bus import EventBus
from lumora_probe.core.config import StartupConfig
from lumora_probe.core.ids import UUIDv7Generator
from lumora_probe.core.logging import get_logger, log_operational
from lumora_probe.core.metrics import MetricRegistry
from lumora_probe.plugins.contracts import PluginDiagnostic, PluginHookObservation
from lumora_probe.shared.events import EventEnvelope, EventOrigin


class _Clock:
    def __init__(self) -> None:
        self.value = 0

    def now(self) -> datetime:
        return datetime(2026, 7, 31, tzinfo=UTC)

    def monotonic_ns(self) -> int:
        self.value += 1
        return self.value


async def _publish_events(metrics: MetricRegistry, count: int) -> None:
    clock = _Clock()
    ids = UUIDv7Generator()
    bus = EventBus(clock=clock, id_generator=ids)
    await metrics.attach(bus)
    for _ in range(count):
        event = EventEnvelope.create(
            event_name="CStoreReceived",
            event_version=1,
            correlation_id=None,
            aggregate_type="Capture",
            aggregate_id="capture-1",
            producer="test",
            payload={},
            origin=EventOrigin.OBSERVED,
            clock=clock,
            id_generator=ids,
        )
        await bus.publish(event)
    await metrics.detach()
    await bus.stop()


@pytest.mark.asyncio
async def test_metrics_are_a_projection_of_published_events() -> None:
    metrics = MetricRegistry()
    await _publish_events(metrics, 3)

    values = {(item.name, item.labels): item.value for item in metrics.snapshot()}
    assert values[("events.total", ())] == 3
    assert values[("events.by_name", (("event_name", "CStoreReceived"),))] == 3
    assert values[("events.by_category", (("category", "DIMSE"),))] == 3


def test_plugin_timing_keeps_slow_tool_named() -> None:
    metrics = MetricRegistry()
    metrics.observe_plugin_timing(
        PluginHookObservation("rules.slow", "analyze", 125_000_000, budget_breach=True)
    )

    plugin_metrics = metrics.plugin_snapshot()["items"]
    assert any(
        item["name"] == "plugin.hook.elapsed_ns" and item["labels"]["plugin_id"] == "rules.slow"
        for item in plugin_metrics
    )
    assert any(
        item["name"] == "plugin.hook.budget_breaches"
        and item["labels"]["plugin_id"] == "rules.slow"
        for item in plugin_metrics
    )


def test_plugin_failure_metric_has_one_counting_path() -> None:
    metrics = MetricRegistry()
    metrics.observe_plugin_timing(PluginHookObservation("p", "analyze", 10, failed=True))
    metrics.observe_plugin_diagnostic(
        PluginDiagnostic("ErrorRaised", "p", "analyze", "failed", elapsed_ns=10)
    )

    errors = [item for item in metrics.snapshot() if item.name == "plugin.hook.errors"]
    assert len(errors) == 1
    assert errors[0].value == 1


def test_alerts_have_hysteresis_states_from_metric_projection() -> None:
    metrics = MetricRegistry()
    metrics.observe_plugin_timing(PluginHookObservation("p", "analyze", 1, failed=True))
    metrics.observe_plugin_diagnostic(PluginDiagnostic("ErrorRaised", "p", "analyze", "failed"))
    alerts = AlertRegistry(
        metrics, AlertThresholds(plugin_errors_warning=1, plugin_errors_critical=2)
    )

    alert = next(item for item in alerts.snapshot() if item.name == "plugin_errors")
    assert alert.state is AlertState.WARNING


def test_audit_categories_are_explicit_and_auth_deferred() -> None:
    assert set(AUDIT_CATEGORY_COVERAGE) == set(AuditCategory)
    assert "Deferred" in AUDIT_CATEGORY_COVERAGE[AuditCategory.LOGIN]
    assert "Deferred" in AUDIT_CATEGORY_COVERAGE[AuditCategory.PERMISSION_CHANGE]


def test_operational_logging_rejects_domain_event_mirrors() -> None:
    with pytest.raises(ValueError, match="must not mirror"):
        log_operational(get_logger("test"), "bad", payload={"event_name": "CStoreReceived"})


def test_production_bootstrap_discovers_plugins_from_canonical_data_path(tmp_path: Path) -> None:
    plugin = tmp_path / "plugins" / "demo.plugin"
    plugin.mkdir(parents=True)
    (plugin / "manifest.json").write_text(
        json.dumps(
            {
                "id": "demo.plugin",
                "name": "Demo",
                "version": "1.0.0",
                "author": "Lumora",
                "description": "test",
                "capabilities": [],
                "sdk": {"min_major": 1, "max_major": 1},
                "entry_point": "plugin:plugin",
                "hooks": ["analyze"],
            }
        ),
        encoding="utf-8",
    )

    application = build_production_app(StartupConfig(data_dir=tmp_path))
    assert application.state.plugin_service.inspect("demo.plugin").health_state == "disabled"


@pytest.mark.asyncio
async def test_production_bootstrap_exposes_health_metrics_audit_and_dashboard(
    tmp_path: Path,
) -> None:
    application = build_production_app(StartupConfig(data_dir=tmp_path))
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        # ASGITransport does not run lifespan; this checks all read-side route composition.
        assert (await client.get("/api/v1/plugins")).status_code == 200
        assert (await client.get("/api/v1/metrics")).status_code == 200
        assert (await client.get("/api/v1/audit")).status_code == 200
        assert (await client.get("/dashboard")).status_code == 200

    health = await application.state.health_registry.check()
    assert health.alive is True
    assert {service.name for service in health.services} >= {
        "event-bus",
        "index-db",
        "app-db",
        "plugin-host",
    }


@pytest.mark.asyncio
async def test_audit_log_persists_configuration_category(tmp_path: Path) -> None:
    application = build_production_app(StartupConfig(data_dir=tmp_path))
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            response = await client.patch("/api/v1/settings", json={"theme": "dark"})
            records = await client.get("/api/v1/audit", params={"category": "ConfigurationChanged"})

    assert response.status_code == 200
    assert records.json()["items"][0]["event_type"] == "ConfigurationChanged"


@pytest.mark.asyncio
async def test_security_failure_audit_is_durable_before_response_completes(tmp_path: Path) -> None:
    application = build_production_app(StartupConfig(data_dir=tmp_path))
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            response = await client.get("/api/v1/health", headers={"host": "untrusted.example"})
        records = await application.state.audit_log.list(category=AuditCategory.SECURITY_FAILURE)

    assert response.status_code == 400
    assert records[0].payload["code"] == "LUMORA-WEB-HOST-001"
