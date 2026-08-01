# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Lumora Probe command-line client and offline capture inspection."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from lumora_probe.plugins import PluginRepository


class ApiClientError(RuntimeError):
    """The live API could not return a usable response."""


class ApiClient:
    """Small synchronous client for live REST resources."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def get(self, path: str) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise ApiClientError(f"Live API request failed: {error}") from error
        if not isinstance(decoded, dict):
            raise ApiClientError("Live API returned a non-object response")
        return cast(dict[str, Any], decoded)


def inspect_capture(path: Path) -> dict[str, Any]:
    """Read a capture manifest without starting application services."""

    if path.is_dir():
        manifest_path = path / "manifest.json"
        raw = manifest_path.read_text(encoding="utf-8")
    elif path.is_file() and path.suffix == ".lpcap":
        with zipfile.ZipFile(path) as archive:
            raw = archive.read("manifest.json").decode("utf-8")
    else:
        raise ApiClientError(f"Capture path is not a directory or .lpcap file: {path}")
    decoded = json.loads(raw)
    if not isinstance(decoded, dict):
        raise ApiClientError("Capture manifest must contain a JSON object")
    return cast(dict[str, Any], decoded)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lumora")
    parser.add_argument("--server", default="http://127.0.0.1:8000", help="live Probe API base URL")
    subparsers = parser.add_subparsers(dest="command", required=True)

    health = subparsers.add_parser("health", help="read live service health")
    health.set_defaults(handler=_run_health)

    captures = subparsers.add_parser("captures", help="read live capture resources")
    capture_subparsers = captures.add_subparsers(dest="captures_command", required=True)
    captures_list = capture_subparsers.add_parser("list", help="list live captures")
    captures_list.set_defaults(handler=_run_captures_list)

    capture = subparsers.add_parser("capture", help="offline capture operations")
    capture_subparsers = capture.add_subparsers(dest="capture_command", required=True)
    inspect_parser = capture_subparsers.add_parser("inspect", help="inspect a local capture")
    inspect_parser.add_argument("path", type=Path)
    inspect_parser.set_defaults(handler=_run_capture_inspect)

    plugins = subparsers.add_parser("plugins", help="manage trusted local plugins")
    plugin_subparsers = plugins.add_subparsers(dest="plugins_command", required=True)
    install = plugin_subparsers.add_parser(
        "install", help="place a plugin on disk; restart is required before loading"
    )
    install.add_argument("source", type=Path)
    install.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("LUMORA_DATA_DIR", "~/.local/share/lumora-probe")),
    )
    install.set_defaults(handler=_run_plugin_install)

    serve = subparsers.add_parser("serve", help="run the Lumora Probe HTTP application")
    serve.add_argument(
        "--trust-network", action="store_true", help="acknowledge non-loopback exposure"
    )
    serve.add_argument("--host", help="override the configured HTTP bind host")
    serve.add_argument("--port", type=int, help="override the configured HTTP port")
    serve.set_defaults(handler=_run_serve)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = args.handler(args)
    except (ApiClientError, OSError, ValueError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1
    if isinstance(result, int):
        return result
    print(json.dumps(result, sort_keys=True))
    return 0


def _run_health(args: argparse.Namespace) -> dict[str, Any]:
    return ApiClient(args.server).get("/api/v1/health")


def _run_serve(args: argparse.Namespace) -> int:
    """Start the production composition root; this is intentionally the only server entry."""
    if args.trust_network:
        os.environ["LUMORA_ALLOW_UNAUTHENTICATED_NETWORK"] = "true"
    if args.host:
        os.environ["LUMORA_BIND_HOST"] = args.host
    if args.port:
        os.environ["LUMORA_PORT"] = str(args.port)
    import uvicorn

    from lumora_probe.bootstrap import build_production_app
    from lumora_probe.core.config import load_startup_config

    config, _sources = load_startup_config()
    uvicorn.run(build_production_app(config), host=config.bind_host, port=config.port)
    return 0


def _run_captures_list(args: argparse.Namespace) -> dict[str, Any]:
    return ApiClient(args.server).get("/api/v1/captures")


def _run_capture_inspect(args: argparse.Namespace) -> dict[str, Any]:
    return inspect_capture(args.path)


def _run_plugin_install(args: argparse.Namespace) -> dict[str, Any]:
    """Copy one deliberately selected plugin directory into the data directory."""

    source = args.source.expanduser().resolve()
    if not source.is_dir():
        raise ApiClientError(f"Plugin source is not a directory: {source}")
    source_repository = PluginRepository(source.parent)
    manifest = source_repository.read_manifest(source)
    destination_root = args.data_dir.expanduser().resolve() / "plugins"
    destination = destination_root / manifest.plugin_id
    if destination.exists():
        raise ApiClientError(f"Plugin is already installed: {manifest.plugin_id}")
    destination_root.mkdir(parents=True, exist_ok=True)
    if any(path.is_symlink() for path in source.rglob("*")):
        raise ApiClientError("Plugin source contains symlinks, which are not installable")
    try:
        destination = destination.resolve()
        if destination.parent != destination_root.resolve():
            raise ApiClientError("Plugin ID must resolve to a direct child of the plugin root")
        temporary = destination_root / f".{manifest.plugin_id}.installing-{os.getpid()}"
        if temporary.exists():
            shutil.rmtree(temporary)
        shutil.copytree(source, temporary, symlinks=False)
        installed = PluginRepository(destination_root).read_manifest(temporary)
        if installed.plugin_id != manifest.plugin_id:
            raise ApiClientError("Plugin manifest changed during installation")
        temporary.replace(destination)
    except Exception:
        if "temporary" in locals() and temporary.exists():  # pyright: ignore[reportPossiblyUnboundVariable]
            shutil.rmtree(temporary, ignore_errors=True)  # pyright: ignore[reportPossiblyUnboundVariable]
        raise
    from lumora_probe.core.audit import AuditCategory, AuditLog
    from lumora_probe.core.clock import SystemClock
    from lumora_probe.core.config import StartupConfig
    from lumora_probe.core.paths import DataPaths
    from lumora_probe.core.storage import StorageDatabases

    paths = DataPaths.from_config(StartupConfig(data_dir=args.data_dir))
    paths.initialise()
    databases = StorageDatabases.from_paths(paths)
    databases.app.initialise()
    AuditLog(databases.app).append_sync(
        AuditCategory.PLUGIN_INSTALLATION,
        entity_type="plugin",
        entity_id=manifest.plugin_id,
        occurred_at=SystemClock().now(),
        payload={"path": str(destination), "version": manifest.version},
    )
    return {
        "installed": manifest.plugin_id,
        "path": str(destination),
        "restart_required": True,
        "trust_notice": "Plugins are trusted in-process code; enabling one can do anything the Lumora process can.",
    }


if __name__ == "__main__":
    raise SystemExit(main())
