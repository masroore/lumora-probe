"""Generate the versioned condition catalogue from the analysis registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lumora_probe.analysis.service import default_condition_registry


def generate_catalog(output: Path) -> None:
    """Write the deterministic condition catalogue artifact."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(default_condition_registry().catalog(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/generated/condition-catalog-v1.json"),
        help="catalog artifact path",
    )
    args = parser.parse_args()
    generate_catalog(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
