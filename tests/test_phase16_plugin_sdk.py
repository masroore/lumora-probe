"""Phase 16 public plugin SDK and containment tests."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from lumora_probe.plugins.contracts import (
    AnalysisContextDTO,
    EventDTO,
    PluginDiagnostic,
)
from lumora_probe.plugins.domain import PluginPolicy, PluginStatus
from lumora_probe.plugins.repository import PluginRepository
from lumora_probe.plugins.service import PluginService


class FakeClock:
    def __init__(self, values: list[int]) -> None:
        self.values = iter(values)

    def monotonic_ns(self) -> int:
        return next(self.values)

    def now(self):
        raise AssertionError("wall clock is not used")


def _write_plugin(
    root: Path,
    *,
    plugin_id: str = "example.plugin",
    sdk_min: int = 1,
    sdk_max: int = 1,
    body: str = """\
from lumora_probe.plugins.api import hookimpl
from lumora_probe.plugins.contracts import FindingDTO

class Plugin:
    @hookimpl
    def analyze(self, context):
        return [FindingDTO('LP-PLUGIN-001', '1', 'plugin-v1', 'certain', (1,), 'ok', ('inspect',))]

plugin = Plugin()
""",
) -> Path:
    path = root / plugin_id
    path.mkdir()
    (path / "manifest.json").write_text(
        json.dumps(
            {
                "id": plugin_id,
                "name": "Example",
                "version": "1.0.0",
                "author": "Lumora",
                "description": "test plugin",
                "capabilities": ["analysis"],
                "sdk": {"min_major": sdk_min, "max_major": sdk_max},
                "entry_point": "plugin:plugin",
                "hooks": ["analyze"],
            }
        ),
        encoding="utf-8",
    )
    (path / "plugin.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def _context() -> AnalysisContextDTO:
    return AnalysisContextDTO(
        events=(
            EventDTO(
                event_id="event-1",
                event_name="AssociationRejected",
                event_version=1,
                sequence=1,
                aggregate_type="Association",
                aggregate_id="a1",
                producer="test",
                payload={},
                origin="observed",
            ),
        )
    )


def test_plugins_are_disabled_until_explicitly_enabled(tmp_path: Path) -> None:
    _write_plugin(tmp_path)
    repository = PluginRepository(tmp_path)
    service = PluginService(repository)

    assert service.records()[0].status is PluginStatus.DISABLED
    service.set_enabled("example.plugin", True)
    assert service.inspect("example.plugin").status is PluginStatus.ENABLED

    reloaded = PluginService(repository)
    assert reloaded.inspect("example.plugin").status is PluginStatus.LOADED
    assert len(reloaded.analyze(_context())) == 1


def test_incompatible_sdk_is_refused_at_load(tmp_path: Path) -> None:
    _write_plugin(tmp_path, sdk_min=2, sdk_max=3)
    repository = PluginRepository(tmp_path)
    repository.set_enabled("example.plugin", True)

    service = PluginService(repository)

    record = service.inspect("example.plugin")
    assert record.status is PluginStatus.INVALID
    assert "incompatible" in (record.last_error or "")


def test_declared_missing_hook_is_structurally_invalid(tmp_path: Path) -> None:
    path = _write_plugin(tmp_path)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    manifest["hooks"] = ["analyze", "on_event"]
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    repository = PluginRepository(tmp_path)
    repository.set_enabled("example.plugin", True)

    record = PluginService(repository).inspect("example.plugin")
    assert record.status is PluginStatus.INVALID
    assert "on_event" in (record.last_error or "")


def test_repeated_plugin_failures_emit_error_and_disable(tmp_path: Path) -> None:
    body = """\
from lumora_probe.plugins.api import hookimpl

class Plugin:
    @hookimpl
    def analyze(self, context):
        raise RuntimeError('boom')

plugin = Plugin()
"""
    _write_plugin(tmp_path, body=body)
    repository = PluginRepository(tmp_path)
    repository.set_enabled("example.plugin", True)
    diagnostics: list[PluginDiagnostic] = []
    service = PluginService(
        repository,
        policy=PluginPolicy(max_failures=2),
        diagnostic_sink=diagnostics.append,
    )

    service.analyze(_context())
    service.analyze(_context())

    assert [item.event_name for item in diagnostics] == ["ErrorRaised", "ErrorRaised"]
    assert service.inspect("example.plugin").status is PluginStatus.FAILED
    assert not repository.is_enabled("example.plugin")


def test_slow_plugin_warns_and_is_disabled_after_repeat(tmp_path: Path) -> None:
    _write_plugin(tmp_path)
    repository = PluginRepository(tmp_path)
    repository.set_enabled("example.plugin", True)
    diagnostics: list[PluginDiagnostic] = []
    service = PluginService(
        repository,
        policy=PluginPolicy(max_failures=2, hook_budget_ns=5),
        clock=FakeClock([0, 10, 20, 30]),
        diagnostic_sink=diagnostics.append,
    )

    service.analyze(_context())
    service.analyze(_context())

    assert [item.event_name for item in diagnostics] == ["WarningRaised", "WarningRaised"]
    assert service.inspect("example.plugin").status is PluginStatus.FAILED
    assert diagnostics[0].budget_ns == 5
