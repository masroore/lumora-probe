"""Command-line and environment configuration for Probe Lite."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PORT = 11112
DEFAULT_AE_TITLE = "PROBE_LITE"
DEFAULT_OUTPUT = Path("./received")
DEFAULT_MAX_PDU = 16382


@dataclass(frozen=True, slots=True)
class Config:
    """Resolved runtime configuration."""

    port: int = DEFAULT_PORT
    ae_title: str = DEFAULT_AE_TITLE
    output: Path = DEFAULT_OUTPUT
    accept_ae: frozenset[str] | None = None
    log_format: str = "text"
    max_pdu: int = DEFAULT_MAX_PDU
    verbose: bool = False


def _env_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean (true/false), got {value!r}")


def _env_int(value: str, name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _parse_accept_ae(value: str | None) -> frozenset[str] | None:
    if value is None:
        return None
    titles = frozenset(item.strip() for item in value.split(",") if item.strip())
    if not titles:
        return None
    return titles


def _validate(config: Config) -> Config:
    if not 1 <= config.port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    if not 1 <= config.max_pdu <= 16_777_215:
        raise ValueError("max-pdu must be between 1 and 16777215")
    if config.log_format not in {"text", "json"}:
        raise ValueError("format must be text or json")
    for name, value in (("AE title", config.ae_title),):
        try:
            encoded = value.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError(f"{name} must contain only ASCII characters") from exc
        if not 1 <= len(encoded) <= 16:
            raise ValueError(f"{name} must be 1 to 16 ASCII characters")
    if config.accept_ae:
        for title in config.accept_ae:
            try:
                encoded = title.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ValueError("accepted AE titles must contain only ASCII characters") from exc
            if not 1 <= len(encoded) <= 16:
                raise ValueError("accepted AE titles must be 1 to 16 ASCII characters")
    return config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="probe-lite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Minimal DICOM C-STORE and C-ECHO receiver. No security. Use on trusted networks only."
        ),
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=None,
        help="TCP listen port (env: PROBE_LITE_PORT; default: 11112)",
    )
    parser.add_argument(
        "-a",
        "--ae",
        dest="ae_title",
        default=None,
        help="Called AE title (env: PROBE_LITE_AE; default: PROBE_LITE)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Instance storage directory (env: PROBE_LITE_OUTPUT; default: ./received)",
    )
    parser.add_argument(
        "--accept-ae",
        default=None,
        help="Comma-separated Calling AE whitelist (env: PROBE_LITE_ACCEPT_AE; default: any)",
    )
    parser.add_argument(
        "-f",
        "--format",
        dest="log_format",
        choices=("text", "json"),
        default=None,
        help="Log format (env: PROBE_LITE_FORMAT; default: text)",
    )
    parser.add_argument(
        "--max-pdu",
        type=int,
        default=None,
        help="Maximum PDU length in bytes (env: PROBE_LITE_MAX_PDU; default: 16382)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=None,
        help="Include DICOM negotiation detail (env: PROBE_LITE_VERBOSE; default: false)",
    )
    from . import __version__

    parser.add_argument("--version", action="version", version=f"probe-lite {__version__}")
    parser.epilog = (
        "Precedence: command-line arguments override environment variables.\n"
        "No security. Use on trusted networks only."
    )
    return parser


def resolve_config(namespace: argparse.Namespace, environ: dict[str, str] | None = None) -> Config:
    env = os.environ if environ is None else environ

    def value(attribute: str, env_name: str, default: object) -> object:
        cli_value = getattr(namespace, attribute)
        return cli_value if cli_value is not None else env.get(env_name, default)

    port_value = value("port", "PROBE_LITE_PORT", DEFAULT_PORT)
    max_pdu_value = value("max_pdu", "PROBE_LITE_MAX_PDU", DEFAULT_MAX_PDU)
    verbose_value = value("verbose", "PROBE_LITE_VERBOSE", False)
    if isinstance(port_value, str):
        port_value = _env_int(port_value, "PROBE_LITE_PORT")
    if isinstance(max_pdu_value, str):
        max_pdu_value = _env_int(max_pdu_value, "PROBE_LITE_MAX_PDU")
    if isinstance(verbose_value, str):
        verbose_value = _env_bool(verbose_value, "PROBE_LITE_VERBOSE")

    accept_value = value("accept_ae", "PROBE_LITE_ACCEPT_AE", None)
    config = Config(
        port=int(port_value),
        ae_title=str(value("ae_title", "PROBE_LITE_AE", DEFAULT_AE_TITLE)),
        output=Path(value("output", "PROBE_LITE_OUTPUT", DEFAULT_OUTPUT)),
        accept_ae=_parse_accept_ae(str(accept_value) if accept_value is not None else None),
        log_format=str(value("log_format", "PROBE_LITE_FORMAT", "text")),
        max_pdu=int(max_pdu_value),
        verbose=bool(verbose_value),
    )
    return _validate(config)


def parse_args(argv: list[str] | None = None, environ: dict[str, str] | None = None) -> Config:
    """Parse CLI arguments and resolve CLI > environment > default precedence."""
    return resolve_config(build_parser().parse_args(argv), environ)
