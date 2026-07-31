"""Phase 16 plugin API trust and restart-scope tests."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from lumora_probe.cli import main
from lumora_probe.web.api import create_app


class Provider:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {
            "example.plugin": {
                "id": "example.plugin",
                "status": "disabled",
                "capabilities": ["analysis"],
                "trusted_code": True,
                "capabilities_enforced": False,
            }
        }

    def records(self) -> Sequence[Mapping[str, Any]]:
        return tuple(self.items.values())

    def inspect(self, plugin_id: str) -> Mapping[str, Any]:
        if plugin_id not in self.items:
            raise KeyError(plugin_id)
        return self.items[plugin_id]

    def set_enabled(self, plugin_id: str, enabled: bool) -> Mapping[str, Any]:
        item = self.items[plugin_id]
        item["status"] = "enabled" if enabled else "disabled"
        return item


def test_plugin_api_lists_and_changes_restart_scoped_state_without_install_route() -> None:
    provider = Provider()
    client = TestClient(create_app(plugin_provider=provider))

    listed = client.get("/api/v1/plugins", headers={"host": "localhost"})
    assert listed.status_code == 200
    assert listed.json()["capabilities_enforced"] is False
    assert "trusted in-process code" in listed.json()["trust_notice"]

    enabled = client.post("/api/v1/plugins/example.plugin/enable", headers={"host": "localhost"})
    assert enabled.status_code == 200
    assert enabled.json()["restart_required"] is True
    assert enabled.json()["plugin"]["status"] == "enabled"

    assert client.post("/api/v1/plugins/install", headers={"host": "localhost"}).status_code in {
        404,
        405,
    }


def test_cli_places_plugin_on_filesystem_and_requires_restart(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source" / "example.plugin"
    source.mkdir(parents=True)
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "id": "example.plugin",
                "name": "Example",
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
    (source / "plugin.py").write_text("plugin = object()\n", encoding="utf-8")

    assert main(["plugins", "install", str(source), "--data-dir", str(tmp_path / "data")]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["installed"] == "example.plugin"
    assert result["restart_required"] is True
    assert (tmp_path / "data" / "plugins" / "example.plugin" / "manifest.json").is_file()


def test_workspace_contains_explicit_plugin_trust_disclosure() -> None:
    template = Path("src/lumora_probe/web/templates/workspace.html").read_text(encoding="utf-8")

    assert "Enabled plugins are trusted in-process code" in template
    assert "capability enforcement is not provided" in template
