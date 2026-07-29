"""Generate the versioned REST API OpenAPI artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lumora_probe.web.api import create_app


def generate_openapi(output: Path) -> None:
    """Write a deterministic OpenAPI document for the current application."""

    output.parent.mkdir(parents=True, exist_ok=True)
    document = create_app().openapi()
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/generated/openapi-v1.json"),
        help="OpenAPI artifact path",
    )
    args = parser.parse_args()
    generate_openapi(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
