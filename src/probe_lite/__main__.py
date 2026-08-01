# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Entry point for ``python -m probe_lite``."""

import sys
from pathlib import Path

# uv run module resolution can lose __package__ context; ensure the
# package root is on sys.path so absolute intra-package imports work.
_pkg_root = str(Path(__file__).resolve().parent.parent)
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from probe_lite.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
