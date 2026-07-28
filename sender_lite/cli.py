"""The ``sender-lite`` command-line entry point."""

from __future__ import annotations

import sys

from .config import parse_args


def main(argv: list[str] | None = None) -> int:
    try:
        parse_args(argv)
    except ValueError as exc:
        print(f"sender-lite: configuration error: {exc}", file=sys.stdout, flush=True)
        return 2
    # Phase 1: config only; orchestration added in later phases.
    return 0
