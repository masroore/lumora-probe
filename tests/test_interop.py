# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Opt-in interoperability suite boundary."""

from __future__ import annotations

import os

import pytest


@pytest.mark.interop
@pytest.mark.slow
def test_interop_suite_is_opt_in() -> None:
    """Keep external implementation checks out of the default quality gate."""
    if os.environ.get("LUMORA_INTEROP") != "1":
        pytest.skip("set LUMORA_INTEROP=1 to run external implementation checks")
