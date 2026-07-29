"""Command-line and TOML configuration for Sender Lite."""

from __future__ import annotations

import argparse
import math
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from lumora_lite_common.config_validators import (
    validate_ae_title,
    validate_log_format,
    validate_max_pdu,
    validate_port,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 11112
DEFAULT_CALLING_AE = "SENDER_LITE"
DEFAULT_CALLED_AE = "PROBE_LITE"
DEFAULT_STUDY_DELAY = 1.0
DEFAULT_CONNECT_TIMEOUT = 10.0
DEFAULT_DIMSE_TIMEOUT = 30.0
DEFAULT_MAX_PDU = 16382
DEFAULT_LOG_FORMAT = "text"

DEFAULT_INPUT = Path("storage/outbox")
DEFAULT_CONFIG_NAME = "sender-lite.toml"

_TOML_FIELDS = frozenset(
    {
        "input",
        "host",
        "port",
        "calling_ae",
        "called_ae",
        "study_delay",
        "connect_timeout",
        "dimse_timeout",
        "max_pdu",
        "log_format",
        "verbose",
    }
)


@dataclass(frozen=True, slots=True)
class Config:
    """Resolved runtime configuration."""

    input: Path | None = DEFAULT_INPUT
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    calling_ae: str = DEFAULT_CALLING_AE
    called_ae: str = DEFAULT_CALLED_AE
    study_delay: float = DEFAULT_STUDY_DELAY
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT
    dimse_timeout: float = DEFAULT_DIMSE_TIMEOUT
    max_pdu: int = DEFAULT_MAX_PDU
    log_format: str = DEFAULT_LOG_FORMAT
    verbose: bool = False
    echo: bool = False
    config_path: Path | None = None


def _validate(config: Config) -> Config:
    if not config.host:
        raise ValueError("host must be a non-empty string")
    validate_port(config.port)
    validate_max_pdu(config.max_pdu)
    validate_log_format(config.log_format)
    validate_ae_title(config.calling_ae, "calling-ae")
    validate_ae_title(config.called_ae, "called-ae")

    for name, value, strict in (
        ("study-delay", config.study_delay, False),
        ("connect-timeout", config.connect_timeout, True),
        ("dimse-timeout", config.dimse_timeout, True),
    ):
        if math.isnan(value) or math.isinf(value):
            raise ValueError(f"{name} must be finite")
        if strict and value <= 0:
            raise ValueError(f"{name} must be greater than zero")
        if not strict and value < 0:
            raise ValueError(f"{name} must be zero or greater")

    if not config.echo and config.input is None:
        raise ValueError("input is required for a Sender Run (provide --input or use --echo)")
    if config.input is not None:
        if config.input.is_symlink():
            raise ValueError(f"input must not be a symlink: {config.input}")
        if not config.input.exists():
            raise ValueError(f"input directory does not exist: {config.input}")
        if not config.input.is_dir():
            raise ValueError(f"input is not a directory: {config.input}")
    return config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sender-lite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("One-shot DICOM C-STORE sender. No security. Use on trusted networks only."),
    )
    parser.add_argument("--config", type=Path, default=None, help="Path to TOML configuration file")
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=None,
        help=f"Input DICOM directory (default: {DEFAULT_INPUT})",
    )
    parser.add_argument("--host", default=None, help=f"Remote host (default: {DEFAULT_HOST})")
    parser.add_argument(
        "-p", "--port", type=int, default=None, help=f"Remote port (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--calling-ae",
        default=None,
        help=f"Calling AE title (default: {DEFAULT_CALLING_AE})",
    )
    parser.add_argument(
        "--called-ae",
        default=None,
        help=f"Called AE title (default: {DEFAULT_CALLED_AE})",
    )
    parser.add_argument(
        "--study-delay",
        type=float,
        default=None,
        help=f"Inter-study delay in seconds (default: {DEFAULT_STUDY_DELAY})",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=None,
        help=f"Association connect timeout (default: {DEFAULT_CONNECT_TIMEOUT})",
    )
    parser.add_argument(
        "--dimse-timeout",
        type=float,
        default=None,
        help=f"DIMSE response timeout (default: {DEFAULT_DIMSE_TIMEOUT})",
    )
    parser.add_argument(
        "--max-pdu",
        type=int,
        default=None,
        help=f"Maximum PDU length in bytes (default: {DEFAULT_MAX_PDU})",
    )
    parser.add_argument(
        "-f",
        "--format",
        dest="log_format",
        choices=("text", "json"),
        default=None,
        help="Log format (default: text)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        dest="verbose",
        default=None,
        help="Include DICOM negotiation detail (default: false)",
    )
    parser.add_argument(
        "--no-verbose",
        action="store_false",
        dest="verbose",
        help="Disable verbose output",
    )
    parser.add_argument(
        "--echo",
        action="store_true",
        default=False,
        help="Run a C-ECHO only (no input directory required)",
    )
    from . import __version__

    parser.add_argument("--version", action="version", version=f"sender-lite {__version__}")
    parser.epilog = (
        "Precedence: CLI arguments override TOML values, which override defaults.\n"
        "No security. Use on trusted networks only."
    )
    return parser


def _check_toml_types(data: dict[str, object], path: Path) -> None:
    for key, value in data.items():
        if key in {"port", "max_pdu"}:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    f"config key {key!r} in {path} must be an integer, got {type(value).__name__}"
                )
        elif key in {"study_delay", "connect_timeout", "dimse_timeout"}:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(
                    f"config key {key!r} in {path} must be a number, got {type(value).__name__}"
                )
        elif key in {"input", "host", "calling_ae", "called_ae", "log_format"}:
            if not isinstance(value, str):
                raise ValueError(
                    f"config key {key!r} in {path} must be a string, got {type(value).__name__}"
                )
        elif key == "verbose" and not isinstance(value, bool):
            raise ValueError(
                f"config key {key!r} in {path} must be a boolean, got {type(value).__name__}"
            )


def _load_toml(path: Path) -> dict[str, object]:
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError as exc:
        raise ValueError(f"config file not found: {path}") from exc
    except OSError as exc:
        raise ValueError(f"cannot read config file {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"config root must be a table: {path}")  # noqa: TRY004  -- all config errors are ValueError/exit-2 per plan §7.5
    unknown = set(data.keys()) - _TOML_FIELDS
    if unknown:
        raise ValueError(f"unknown config key(s) in {path}: {', '.join(sorted(unknown))}")
    _check_toml_types(data, path)
    return data


def _discover_config_path(cli_config: Path | None, cwd: Path) -> Path | None:
    if cli_config is not None:
        return cli_config if cli_config.is_absolute() else cwd / cli_config
    default = cwd / DEFAULT_CONFIG_NAME
    if default.is_file():
        return default
    return None


def resolve_config(
    namespace: argparse.Namespace,
    cwd: Path | None = None,
) -> Config:
    cwd = Path.cwd() if cwd is None else cwd

    config_path = _discover_config_path(namespace.config, cwd)

    toml_data: dict[str, object] = {}
    toml_dir: Path | None = None
    if config_path is not None:
        toml_data = _load_toml(config_path)
        toml_dir = config_path.parent

    def pick_str(attr: str, toml_key: str, default: str) -> tuple[str, str]:
        cli_value = getattr(namespace, attr, None)
        if cli_value is not None:
            return str(cli_value), "cli"
        if toml_key in toml_data:
            return str(toml_data[toml_key]), "toml"
        return default, "default"

    def pick_int(attr: str, toml_key: str, default: int) -> tuple[int, str]:
        cli_value = getattr(namespace, attr, None)
        if cli_value is not None:
            return int(cli_value), "cli"
        if toml_key in toml_data:
            value = toml_data[toml_key]
            if isinstance(value, bool):
                raise ValueError(f"{toml_key} must be an integer, got boolean")
            if not isinstance(value, int):
                raise ValueError(f"{toml_key} must be an integer")
            return value, "toml"
        return default, "default"

    def pick_float(attr: str, toml_key: str, default: float) -> tuple[float, str]:
        cli_value = getattr(namespace, attr, None)
        if cli_value is not None:
            return float(cli_value), "cli"
        if toml_key in toml_data:
            value = toml_data[toml_key]
            if isinstance(value, bool):
                raise ValueError(f"{toml_key} must be a number, got boolean")
            if not isinstance(value, (int, float)):
                raise ValueError(f"{toml_key} must be a number")
            return float(value), "toml"
        return default, "default"

    def pick_bool(attr: str, toml_key: str, default: bool) -> tuple[bool, str]:
        cli_value = getattr(namespace, attr, None)
        if cli_value is not None:
            return bool(cli_value), "cli"
        if toml_key in toml_data:
            return bool(toml_data[toml_key]), "toml"
        return default, "default"

    input_cli = namespace.input
    input_src = "cli" if input_cli is not None else ("toml" if "input" in toml_data else "default")
    input_value: str | None
    if input_cli is not None:
        input_value = str(input_cli)
    elif "input" in toml_data:
        input_value = str(toml_data["input"])
    else:
        input_value = None

    host, _ = pick_str("host", "host", DEFAULT_HOST)
    port, _ = pick_int("port", "port", DEFAULT_PORT)
    calling_ae, _ = pick_str("calling_ae", "calling_ae", DEFAULT_CALLING_AE)
    called_ae, _ = pick_str("called_ae", "called_ae", DEFAULT_CALLED_AE)
    study_delay, _ = pick_float("study_delay", "study_delay", DEFAULT_STUDY_DELAY)
    connect_timeout, _ = pick_float("connect_timeout", "connect_timeout", DEFAULT_CONNECT_TIMEOUT)
    dimse_timeout, _ = pick_float("dimse_timeout", "dimse_timeout", DEFAULT_DIMSE_TIMEOUT)
    max_pdu, _ = pick_int("max_pdu", "max_pdu", DEFAULT_MAX_PDU)
    log_format, _ = pick_str("log_format", "log_format", DEFAULT_LOG_FORMAT)
    verbose, _ = pick_bool("verbose", "verbose", False)

    input_path: Path | None = None
    if input_value is not None:
        candidate = Path(input_value)
        if input_src == "toml" and toml_dir is not None and not candidate.is_absolute():
            candidate = toml_dir / candidate
        elif input_src == "cli" and not candidate.is_absolute():
            candidate = cwd / candidate
        input_path = candidate
    elif not namespace.echo:
        input_path = DEFAULT_INPUT

    config = Config(
        input=input_path,
        host=host,
        port=port,
        calling_ae=calling_ae,
        called_ae=called_ae,
        study_delay=study_delay,
        connect_timeout=connect_timeout,
        dimse_timeout=dimse_timeout,
        max_pdu=max_pdu,
        log_format=log_format,
        verbose=verbose,
        echo=bool(namespace.echo),
        config_path=config_path,
    )
    return _validate(config)


def parse_args(
    argv: list[str] | None = None,
    cwd: Path | None = None,
) -> Config:
    """Parse CLI arguments and resolve CLI > TOML > defaults precedence."""
    if argv is None:
        argv = sys.argv[1:]
    cwd = Path.cwd() if cwd is None else cwd

    # Zero args + no default config -> configuration error.
    if len(argv) == 0:
        default_config = cwd / DEFAULT_CONFIG_NAME
        if not default_config.is_file():
            raise ValueError(
                f"no arguments and no {DEFAULT_CONFIG_NAME} found; "
                "provide --input or --echo, or create a config file"
            )

    parser = build_parser()
    namespace = parser.parse_args(argv)
    return resolve_config(namespace, cwd)
