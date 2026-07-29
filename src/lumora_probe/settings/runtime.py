"""Persistent live settings with provenance and source-lock enforcement."""

from __future__ import annotations

import os
import tempfile
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lumora_probe.core.errors import ConfigurationError, RestartRequiredError, SettingLockedError


class SettingSource(StrEnum):
    DEFAULT = "default"
    FILE = "file"
    ENV = "env"
    RUNTIME = "runtime"


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ring_buffer_seconds: int = Field(default=300, ge=1, le=86400)
    ring_buffer_max_mb: int = Field(default=512, ge=1, le=102400)
    decode_cache_max_mb: int = Field(default=512, ge=1, le=102400)
    ae_allowlist: tuple[str, ...] = ()
    ip_allowlist: tuple[str, ...] = ()
    read_only: bool = False
    theme: str = "system"
    rule_set_toggles: dict[str, bool] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SettingSnapshot:
    name: str
    value: Any
    source: str


_STARTUP_ONLY = frozenset(
    {
        "data_dir",
        "captures_root",
        "additional_capture_roots",
        "bind_host",
        "port",
        "dicom_port",
        "executor_workers",
        "shutdown_grace_seconds",
    }
)
_ENV_NAMES = {
    "ring_buffer_seconds": "LUMORA_RING_BUFFER_SECONDS",
    "ring_buffer_max_mb": "LUMORA_RING_BUFFER_MAX_MB",
    "decode_cache_max_mb": "LUMORA_DECODE_CACHE_MAX_MB",
    "ae_allowlist": "LUMORA_AE_ALLOWLIST",
    "ip_allowlist": "LUMORA_IP_ALLOWLIST",
    "read_only": "LUMORA_READ_ONLY",
    "theme": "LUMORA_THEME",
}


def _parse_env(field: str, value: str) -> Any:
    if field in {"ae_allowlist", "ip_allowlist"}:
        return tuple(item.strip() for item in value.split(",") if item.strip())
    return value


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value: {type(value).__name__}")


def _render_toml(values: Mapping[str, Any]) -> str:
    lines: list[str] = []
    nested: dict[str, Mapping[str, Any]] = {}
    for key, value in values.items():
        if isinstance(value, dict):
            nested[key] = value
        else:
            lines.append(f"{key} = {_toml_value(value)}")
    for table, table_values in nested.items():
        lines.extend(["", f"[{table}]"])
        lines.extend(f"{key} = {_toml_value(value)}" for key, value in table_values.items())
    return "\n".join(lines) + "\n"


class RuntimeSettingsStore:
    """Load, inspect, and atomically update settings.toml under the data root."""

    def __init__(self, path: Path, *, environ: Mapping[str, str] | None = None) -> None:
        self.path = path
        self.environ = dict(os.environ if environ is None else environ)
        self._settings: RuntimeSettings | None = None
        self._sources: dict[str, str] = {}

    def load(self) -> RuntimeSettings:
        file_values: dict[str, Any] = {}
        if self.path.is_file():
            try:
                with self.path.open("rb") as handle:
                    loaded = tomllib.load(handle)
                file_values = dict(loaded)
            except (OSError, tomllib.TOMLDecodeError) as exc:
                raise ConfigurationError(
                    code="LUMORA-CORE-SETTINGS-001",
                    message=f"Unable to read runtime settings: {self.path}",
                    remediation="Fix settings.toml syntax or restore the last valid copy.",
                    context={"path": str(self.path)},
                ) from exc
        values = RuntimeSettings().model_dump()
        values.update(file_values)
        self._sources = {key: SettingSource.DEFAULT for key in values}
        self._sources.update({key: SettingSource.FILE for key in file_values})
        for field, env_name in _ENV_NAMES.items():
            if env_name in self.environ:
                values[field] = _parse_env(field, self.environ[env_name])
                self._sources[field] = SettingSource.ENV
        try:
            self._settings = RuntimeSettings.model_validate(values)
        except ValidationError as exc:
            first = exc.errors()[0]
            field = str(first.get("loc", ("settings",))[0])
            raise ConfigurationError(
                code="LUMORA-CORE-SETTINGS-002",
                message=f"Invalid runtime setting {field!r} from {self._sources.get(field, SettingSource.DEFAULT)}",
                remediation="Correct the value in settings.toml or its environment variable.",
                context={
                    "key": field,
                    "source": self._sources.get(field, SettingSource.DEFAULT),
                    "errors": exc.errors(),
                },
            ) from exc
        return self._settings

    @property
    def settings(self) -> RuntimeSettings:
        return self._settings or self.load()

    def snapshot(self, name: str) -> SettingSnapshot:
        settings = self.settings
        if not hasattr(settings, name):
            raise KeyError(name)
        return SettingSnapshot(
            name, getattr(settings, name), self._sources.get(name, SettingSource.DEFAULT)
        )

    def snapshots(self) -> tuple[SettingSnapshot, ...]:
        return tuple(self.snapshot(name) for name in self.settings.model_fields)

    def update(self, name: str, value: Any) -> SettingSnapshot:
        if name in _STARTUP_ONLY:
            raise RestartRequiredError(
                code="LUMORA-CORE-SETTINGS-003",
                message=f"Setting {name!r} requires a restart",
                remediation="Change the startup configuration and restart Lumora Probe.",
                context={
                    "setting": name,
                    "source": self._sources.get(name, SettingSource.DEFAULT),
                    "restart_required": True,
                },
            )
        current = self.snapshot(name)
        if current.source in {SettingSource.FILE, SettingSource.ENV}:
            raise SettingLockedError(
                code="LUMORA-CORE-SETTINGS-004",
                message=f"Setting {name!r} is locked by {current.source}",
                remediation="Change the owning source, then restart or reload the setting explicitly.",
                context={"setting": name, "source": current.source},
            )
        values = self.settings.model_dump()
        values[name] = value
        try:
            updated = RuntimeSettings.model_validate(values)
        except ValidationError as exc:
            raise ConfigurationError(
                code="LUMORA-CORE-SETTINGS-005",
                message=f"Invalid runtime setting {name!r}",
                remediation="Use a value accepted by the setting schema.",
                context={"setting": name, "errors": exc.errors()},
            ) from exc
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(updated.model_dump())
        self._settings = updated
        self._sources[name] = SettingSource.RUNTIME
        return self.snapshot(name)

    def _atomic_write(self, values: Mapping[str, Any]) -> None:
        fd, temporary_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(_render_toml(values))
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
