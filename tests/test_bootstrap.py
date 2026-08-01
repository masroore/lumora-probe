# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Production composition-root acceptance tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from lumora_probe.bootstrap import build_production_app, build_production_runtime
from lumora_probe.core.config import StartupConfig
from lumora_probe.core.errors import LifecycleError
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


def test_bootstrap_exposes_lifecycle_manager(tmp_path: Path) -> None:
    """build_production_app wires a LifecycleManager onto application.state."""
    from lumora_probe.core.lifecycle import LifecycleManager

    application = build_production_app(StartupConfig(data_dir=tmp_path))

    assert hasattr(application.state, "lifecycle_manager")
    assert isinstance(application.state.lifecycle_manager, LifecycleManager)


@pytest.mark.component
@pytest.mark.slow
@pytest.mark.asyncio
async def test_production_runtime_forced_deadline_interrupts_active_capture(
    tmp_path: Path, unused_tcp_port: int, unused_tcp_port_factory: object
) -> None:
    runtime = build_production_runtime(
        StartupConfig(
            data_dir=tmp_path,
            port=unused_tcp_port,
            dicom_port=unused_tcp_port_factory(),
            shutdown_grace_seconds=0.05,
        )
    )
    await runtime.lifecycle.start()
    capture_id = await runtime.capture_engine.start_session(source="forced-deadline-test")
    original_drain = runtime.capture_engine.drain
    drain_entered = asyncio.Event()
    drain_calls = 0

    async def block_first_drain() -> None:
        nonlocal drain_calls
        drain_calls += 1
        if drain_calls == 1:
            drain_entered.set()
            await asyncio.Event().wait()
        await original_drain()

    runtime.capture_engine.drain = block_first_drain  # type: ignore[method-assign]
    try:
        shutdown = asyncio.create_task(runtime.lifecycle.shutdown(grace_seconds=0.05))
        await asyncio.wait_for(drain_entered.wait(), 1)
        with pytest.raises(LifecycleError, match="exceeded"):
            await asyncio.wait_for(shutdown, 2)

        manifest = await runtime.capture_engine.interrupt_session(
            capture_id, reason="test deadline"
        )
        assert manifest.state == "interrupted"
        assert manifest.interruption_reason == "shutdown deadline"
        assert not runtime.capture_engine.sessions
    finally:
        if runtime.lifecycle.state.value != "stopped":
            await runtime.lifecycle.shutdown(grace_seconds=2)
