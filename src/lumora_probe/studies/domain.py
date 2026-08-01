# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Pure domain errors and invariants for the study viewer."""

from __future__ import annotations

from .contracts import DecodeFailure, DecodeFailureKind


class DecodeError(ValueError):
    """Raised at the decode boundary with a user-actionable explanation."""

    def __init__(self, failure: DecodeFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


def failure(
    kind: DecodeFailureKind,
    message: str,
    remediation: str,
    **context: object,
) -> DecodeError:
    """Build one normalized decode error."""
    return DecodeError(DecodeFailure(kind, message, remediation, context))


__all__: tuple[str, ...] = ()
