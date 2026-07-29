"""Generate the versioned event catalog artifact from the shared registry."""

from __future__ import annotations

import argparse
from pathlib import Path

from lumora_probe.shared.events import DEFAULT_EVENT_REGISTRY


def generate_catalog(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(DEFAULT_EVENT_REGISTRY.catalog_json())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/generated/event-catalog-v1.json"),
        help="catalog artifact path",
    )
    args = parser.parse_args()
    generate_catalog(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
