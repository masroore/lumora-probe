# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Deterministic UUIDv7 identity source for component tests."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from lumora_probe.core.ids import SeededUUIDv7Generator


class SeededIdGenerator(SeededUUIDv7Generator):
    """Readable test-double alias for the injected ID protocol."""

    def __init__(self, values: Iterable[UUID | str]) -> None:
        super().__init__(values)
