"""Production composition-root acceptance tests."""

from __future__ import annotations

from pathlib import Path

from lumora_probe.bootstrap import build_production_app
from lumora_probe.core.config import StartupConfig
from lumora_probe.plugins.contracts import PluginDiagnostic


def test_bootstrap_wires_plugin_service_with_clock(tmp_path: Path) -> None:
    application = build_production_app(StartupConfig(data_dir=tmp_path))

    assert application.state.plugin_service.clock is not None
    assert application.state.paths.plugins.is_dir()


def test_bootstrap_plugin_provider_returns_dicts(tmp_path: Path) -> None:
    application = build_production_app(StartupConfig(data_dir=tmp_path))

    assert application.state.plugin_service.records() == ()
    assert application.state.plugin_provider.records() == ()


def test_bootstrap_creates_plugin_directory(tmp_path: Path) -> None:
    application = build_production_app(StartupConfig(data_dir=tmp_path))

    assert application.state.paths.plugins == tmp_path / "plugins"
    assert application.state.paths.plugins.exists()


def test_bootstrap_diagnostic_sink_receives_failures(tmp_path: Path) -> None:
    application = build_production_app(StartupConfig(data_dir=tmp_path))
    sink = application.state.plugin_service.diagnostic_sink
    assert sink is not None

    sink(PluginDiagnostic("ErrorRaised", "demo.plugin", "analyze", "failed"))
    assert any(item.name == "plugin.hook.errors" for item in application.state.metrics.snapshot())


def test_empty_plugin_dir_returns_empty_list(tmp_path: Path) -> None:
    application = build_production_app(StartupConfig(data_dir=tmp_path))

    assert application.state.plugin_service.records() == ()
