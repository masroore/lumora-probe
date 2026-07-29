"""Immutable startup configuration and source/provenance resolution."""

from __future__ import annotations

import ipaddress
import os
import platform
import re
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .errors import ConfigurationError, NetworkExposureError


class ConfigSource(StrEnum):
    """Source precedence exposed to operators."""

    DEFAULT = "default"
    FILE = "file"
    ENV = "env"


class StartupConfig(BaseSettings):
    """Settings fixed for the lifetime of a process."""

    model_config = SettingsConfigDict(
        frozen=True, extra="forbid", validate_assignment=True, env_prefix="LUMORA_"
    )

    data_dir: Path
    captures_root: Path | None = None
    additional_capture_roots: tuple[Path, ...] = ()
    bind_host: str = "127.0.0.1"
    dicom_bind_host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    dicom_port: int = Field(default=11112, ge=1, le=65535)
    allow_unauthenticated_network: bool = False
    executor_workers: int = Field(default=4, ge=1, le=256)
    shutdown_grace_seconds: float = Field(default=10.0, gt=0, le=300)
    read_only: bool = False

    @field_validator("bind_host", "dicom_bind_host")
    @classmethod
    def validate_bind_host(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("must not be empty")
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            if any(character.isspace() for character in candidate):
                raise ValueError("must be an IP address or hostname") from None
        return candidate

    @field_validator("data_dir", "captures_root", mode="before")
    @classmethod
    def normalize_path(cls, value: Any) -> Any:
        if value is None:
            return value
        return Path(value).expanduser()

    @field_validator("additional_capture_roots", mode="before")
    @classmethod
    def normalize_roots(cls, value: Any) -> Any:
        if value is None:
            return ()
        if isinstance(value, (str, Path)):
            value = [value]
        return tuple(Path(item).expanduser() for item in value)

    def effective_captures_root(self) -> Path:
        return (self.captures_root or self.data_dir / "captures").resolve()

    def source_for(self, field_name: str, sources: Mapping[str, ConfigSource]) -> ConfigSource:
        return sources.get(field_name, ConfigSource.DEFAULT)


_ENV_NAMES: dict[str, str] = {
    "data_dir": "LUMORA_DATA_DIR",
    "captures_root": "LUMORA_CAPTURES_ROOT",
    "additional_capture_roots": "LUMORA_ADDITIONAL_CAPTURE_ROOTS",
    "bind_host": "LUMORA_BIND_HOST",
    "dicom_bind_host": "LUMORA_DICOM_BIND_HOST",
    "port": "LUMORA_PORT",
    "dicom_port": "LUMORA_DICOM_PORT",
    "allow_unauthenticated_network": "LUMORA_ALLOW_UNAUTHENTICATED_NETWORK",
    "executor_workers": "LUMORA_EXECUTOR_WORKERS",
    "shutdown_grace_seconds": "LUMORA_SHUTDOWN_GRACE_SECONDS",
    "read_only": "LUMORA_READ_ONLY",
}

_DEFAULT_CONFIG_NAMES = ("lumora.toml", ".lumora.toml", "lumora.yaml", "lumora.yml")


def default_data_dir(
    *, system: str | None = None, environ: Mapping[str, str] | None = None
) -> Path:
    """Return the platform-conventional data root without touching the filesystem."""

    env = os.environ if environ is None else environ
    system_name = (system or platform.system()).lower()
    if system_name == "darwin":
        return Path.home() / "Library" / "Application Support" / "Lumora Probe"
    if system_name == "windows":
        return Path(env.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Lumora Probe"
    return Path(env.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "lumora-probe"


def _parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigurationError(
                code="LUMORA-CORE-CONFIG-001",
                message=f"Malformed .env entry at {path}:{line_number}",
                remediation="Use KEY=value syntax or remove the malformed line.",
                context={"source": str(path), "line": line_number},
            )
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _load_file(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".toml":
        import tomllib

        with path.open("rb") as handle:
            loaded = tomllib.load(handle)
    else:
        loaded = _parse_simple_yaml(path)
    return loaded


def _parse_simple_yaml(path: Path) -> dict[str, Any]:
    """Parse the flat scalar/list YAML subset used by startup configuration.

    Full YAML is intentionally not added as a runtime dependency. Nested YAML is rejected
    rather than interpreted ambiguously; TOML remains the preferred configuration format.
    """

    import ast

    values: dict[str, Any] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-", " ")) or ":" not in line:
            raise ConfigurationError(
                code="LUMORA-CORE-CONFIG-003",
                message=f"Unsupported YAML syntax at {path}:{line_number}",
                remediation="Use flat key: value entries or switch to TOML.",
                context={"source": str(path), "line": line_number},
            )
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key:
            raise ConfigurationError(
                code="LUMORA-CORE-CONFIG-004",
                message=f"Empty YAML key at {path}:{line_number}",
                remediation="Name the setting or remove the entry.",
                context={"source": str(path), "line": line_number},
            )
        try:
            values[key] = ast.literal_eval(raw_value)
        except (ValueError, SyntaxError):
            values[key] = raw_value.strip('"').strip("'")
    return values


def _find_config_file(cwd: Path, environ: Mapping[str, str]) -> Path | None:
    explicit = environ.get("LUMORA_CONFIG_FILE")
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise ConfigurationError(
                code="LUMORA-CORE-CONFIG-005",
                message=f"Configured startup file does not exist: {path}",
                remediation="Create the file or unset LUMORA_CONFIG_FILE.",
                context={"key": "LUMORA_CONFIG_FILE", "source": "env"},
            )
        return path
    for name in _DEFAULT_CONFIG_NAMES:
        candidate = cwd / name
        if candidate.is_file():
            return candidate
    return None


def _coerce_env_value(field_name: str, value: str) -> Any:
    if field_name in {"additional_capture_roots"}:
        return tuple(item.strip() for item in value.split(os.pathsep) if item.strip())
    return value


def _normalise_file_key(key: str) -> str:
    aliases = {value: name for name, value in _ENV_NAMES.items()}
    return aliases.get(key, key)


def _validate_network_gate(config: StartupConfig, sources: Mapping[str, ConfigSource]) -> None:
    for field_name in ("bind_host", "dicom_bind_host"):
        host = getattr(config, field_name)
        try:
            address = ipaddress.ip_address(host)
            is_loopback = address.is_loopback
        except ValueError:
            is_loopback = host.lower() in {"localhost", "localhost.localdomain"}
        if not is_loopback and not config.allow_unauthenticated_network:
            source = sources.get(field_name, ConfigSource.DEFAULT)
            raise NetworkExposureError(
                code="LUMORA-CORE-NETWORK-001",
                message=f"Refusing non-loopback {field_name} {host!r} without acknowledgment",
                remediation="Bind to 127.0.0.1 or set allow_unauthenticated_network=true / "
                "LUMORA_ALLOW_UNAUTHENTICATED_NETWORK=true / --trust-network.",
                context={field_name: host, "source": source.value},
            )


def load_startup_config(
    *,
    environ: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    system: str | None = None,
) -> tuple[StartupConfig, dict[str, ConfigSource]]:
    """Resolve and validate immutable startup settings.

    Precedence is environment > ``.env`` > TOML/YAML > defaults. The returned source map
    lets API and UI layers explain why a value is locked.
    """

    env = dict(os.environ if environ is None else environ)
    working_directory = (cwd or Path.cwd()).resolve()
    config_file = _find_config_file(working_directory, env)
    dotenv_file = working_directory / ".env"
    file_values = _load_file(config_file) if config_file else {}
    dotenv_values = _parse_dotenv(dotenv_file)

    values: dict[str, Any] = {
        "data_dir": default_data_dir(system=system, environ=env),
    }
    sources: dict[str, ConfigSource] = {
        field_name: ConfigSource.DEFAULT for field_name in _ENV_NAMES
    }
    for raw_key, value in file_values.items():
        key = _normalise_file_key(str(raw_key))
        values[key] = value
        sources[key] = ConfigSource.FILE
    for field_name, env_name in _ENV_NAMES.items():
        if env_name in dotenv_values:
            values[field_name] = _coerce_env_value(field_name, dotenv_values[env_name])
            sources[field_name] = ConfigSource.ENV
        if env_name in env:
            values[field_name] = _coerce_env_value(field_name, env[env_name])
            sources[field_name] = ConfigSource.ENV
    try:
        config = StartupConfig.model_validate(values)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        location = str(first_error.get("loc", ("configuration",))[0])
        source = sources.get(location, ConfigSource.DEFAULT)
        raise ConfigurationError(
            code="LUMORA-CORE-CONFIG-006",
            message=f"Invalid configuration key {location!r} from {source.value}",
            remediation="Correct the value in the named source; startup will not silently default it.",
            context={
                "key": location,
                "source": source.value,
                "source_file": str(
                    config_file or dotenv_file if source != ConfigSource.DEFAULT else "default"
                ),
                "errors": exc.errors(),
            },
        ) from exc
    _validate_network_gate(config, sources)
    return config, sources


def is_loopback_host(host: str) -> bool:
    """Return whether a bind host is loopback-only."""

    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() in {"localhost", "localhost.localdomain"}


_UUID7_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-7[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


def is_uuid7(value: str) -> bool:
    return bool(_UUID7_RE.fullmatch(value))
