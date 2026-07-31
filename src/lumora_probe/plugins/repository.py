"""Filesystem discovery and restart-scoped plugin state."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from .contracts import PluginHookName
from .domain import PluginManifest, PluginRecord, PluginStatus

_STATE_FILE = ".plugin-state.json"
_MANIFEST_FILE = "manifest.json"


class PluginRepository:
    """Discover plugin directories and persist only deliberate enablement state."""

    def __init__(self, plugins_root: Path) -> None:
        self.plugins_root = plugins_root.expanduser().resolve()
        self.plugins_root.mkdir(parents=True, exist_ok=True)

    def discover(self) -> tuple[PluginManifest, ...]:
        """Return structurally parsed manifests in deterministic ID order."""

        manifests: list[PluginManifest] = []
        for path in sorted(self.plugins_root.iterdir(), key=lambda candidate: candidate.name):
            if not path.is_dir() or path.name.startswith("."):
                continue
            manifest_path = path / _MANIFEST_FILE
            if not manifest_path.is_file():
                continue
            try:
                manifests.append(self._read_manifest(path, manifest_path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return tuple(sorted(manifests, key=lambda manifest: manifest.plugin_id))

    def read_manifest(self, plugin_path: Path) -> PluginManifest:
        """Read and validate one plugin manifest."""

        path = plugin_path.expanduser().resolve()
        if path.parent != self.plugins_root or not path.is_dir():
            raise ValueError("plugin path must be a direct child of the plugin root")
        return self._read_manifest(path, path / _MANIFEST_FILE)

    def records(self) -> tuple[PluginRecord, ...]:
        """Return discovered plugin records; plugins are disabled unless explicitly enabled."""

        enabled = self._enabled_ids()
        return tuple(
            PluginRecord(
                manifest=manifest,
                status=PluginStatus.ENABLED
                if manifest.plugin_id in enabled
                else PluginStatus.DISABLED,
            )
            for manifest in self.discover()
        )

    def is_enabled(self, plugin_id: str) -> bool:
        """Return persisted enablement state."""

        return plugin_id in self._enabled_ids()

    def set_enabled(self, plugin_id: str, enabled: bool) -> PluginManifest:
        """Persist enablement for the next process restart."""

        manifest = next(
            (candidate for candidate in self.discover() if candidate.plugin_id == plugin_id), None
        )
        if manifest is None:
            raise KeyError(f"unknown plugin: {plugin_id}")
        current = self._enabled_ids()
        if enabled:
            current.add(plugin_id)
        else:
            current.discard(plugin_id)
        self._write_enabled_ids(current)
        return manifest

    def install_directory(self, source: Path) -> PluginManifest:
        """Copying is intentionally outside this repository; validate an installed directory."""

        return self.read_manifest(source)

    def _read_manifest(self, path: Path, manifest_path: Path) -> PluginManifest:
        if not manifest_path.is_file():
            raise ValueError("plugin manifest.json is missing")
        decoded = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(decoded, dict):
            raise TypeError("plugin manifest must be a JSON object")
        values = cast(dict[str, Any], decoded)
        sdk_value = values.get("sdk")
        sdk = cast(dict[str, Any], sdk_value) if isinstance(sdk_value, dict) else None
        if not isinstance(sdk, dict):
            raise TypeError("plugin manifest sdk must be an object")
        hooks_value = values.get("hooks")
        hooks_raw = cast(list[Any], hooks_value) if isinstance(hooks_value, list) else None
        if not isinstance(hooks_raw, list) or not hooks_raw:
            raise TypeError("plugin manifest hooks must be a non-empty array")
        try:
            hooks = tuple(PluginHookName(value) for value in hooks_raw)
        except ValueError as error:
            raise ValueError(f"plugin manifest declares an unknown hook: {error}") from error
        capabilities_value = values.get("capabilities", [])
        capabilities = (
            cast(list[Any], capabilities_value) if isinstance(capabilities_value, list) else None
        )
        if not isinstance(capabilities, list) or not all(
            isinstance(item, str) for item in capabilities
        ):
            raise TypeError("plugin manifest capabilities must be an array of strings")
        return PluginManifest(
            plugin_id=_required_text(values, "id"),
            name=_required_text(values, "name"),
            version=_required_text(values, "version"),
            author=_required_text(values, "author"),
            description=_required_text(values, "description"),
            capabilities=tuple(capabilities),
            sdk_min=_required_int(sdk, "min_major"),
            sdk_max=_required_int(sdk, "max_major"),
            entry_point=_required_text(values, "entry_point"),
            hooks=hooks,
            path=path,
        )

    def _enabled_ids(self) -> set[str]:
        path = self.plugins_root / _STATE_FILE
        if not path.is_file():
            return set()
        decoded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(decoded, dict):
            raise TypeError("plugin state must be a JSON object")
        raw_values = cast(dict[str, Any], decoded).get("enabled", [])
        values = cast(list[Any], raw_values)
        if not all(isinstance(value, str) for value in values):
            raise ValueError("plugin state enabled must be an array of strings")
        return set(values)

    def _write_enabled_ids(self, enabled: Iterable[str]) -> None:
        path = self.plugins_root / _STATE_FILE
        path.write_text(
            json.dumps({"enabled": sorted(set(enabled))}, indent=2) + "\n",
            encoding="utf-8",
        )


def _required_text(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if type(value) is not str or not value.strip():
        raise ValueError(f"plugin manifest {key} must be a non-empty string")
    return value.strip()


def _required_int(values: dict[str, Any], key: str) -> int:
    value = values.get(key)
    if type(value) is not int or isinstance(value, bool):
        raise ValueError(f"plugin manifest sdk.{key} must be an integer")
    return value


__all__: tuple[str, ...] = ()
