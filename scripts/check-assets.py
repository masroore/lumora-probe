"""Fail when committed frontend artifacts differ from a clean build."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run(["npm", "ci"], check=True)
    subprocess.run(["npm", "run", "build:assets"], check=True)
    result = subprocess.run(
        ["git", "diff", "--exit-code", "--", "static", "assets/vendor"], check=False
    )
    if result.returncode:
        print(
            "Committed assets are stale; run npm run build:assets and commit the outputs.",
            file=sys.stderr,
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
