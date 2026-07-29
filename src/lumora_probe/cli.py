"""Lumora Probe command-line client and offline capture inspection."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = args.handler(args)
    except (ApiClientError, OSError, ValueError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


def _run_health(args: argparse.Namespace) -> dict[str, Any]:
    return ApiClient(args.server).get("/api/v1/health")


def _run_captures_list(args: argparse.Namespace) -> dict[str, Any]:
    return ApiClient(args.server).get("/api/v1/captures")


def _run_capture_inspect(args: argparse.Namespace) -> dict[str, Any]:
    return inspect_capture(args.path)


if __name__ == "__main__":
    raise SystemExit(main())
