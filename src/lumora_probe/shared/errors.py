# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Domain errors with stable operator-facing context."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lumora_probe.core.errors import LumoraError


class DomainError(LumoraError):
    """Base class for invariant and lifecycle failures in the domain."""


class DomainInvariantError(DomainError):
    """A domain value or aggregate invariant was violated."""


class InvalidStateTransitionError(DomainError):
    """An aggregate cannot perform an operation from its current state."""


class AssociationDomainError(DomainError):
    """An association or association-pair operation failed."""


class CaptureDomainError(DomainError):
    """A capture operation failed."""


class ReplayDomainError(DomainError):
    """A replay operation failed."""


class ReportDomainError(DomainError):
    """A report operation failed."""


# Short names keep domain code readable while preserving explicit taxonomy names.
InvariantViolationError = DomainInvariantError
StateTransitionError = InvalidStateTransitionError


def domain_invariant(
    message: str,
    *,
    field: str,
    value: Any = None,
    remediation: str = "Provide a value that satisfies the domain invariant.",
) -> DomainInvariantError:
    """Build a structured invariant error without leaking boundary vocabulary."""
    context: Mapping[str, Any] = {"field": field}
    if value is not None:
        context = {"field": field, "value": value}
    return DomainInvariantError(
        code="LUMORA-DOMAIN-INV-001",
        message=message,
        remediation=remediation,
        context=context,
    )


def invalid_transition(
    aggregate: str,
    state: str,
    operation: str,
    allowed_states: tuple[str, ...],
) -> InvalidStateTransitionError:
    """Build a structured lifecycle transition error."""
    return InvalidStateTransitionError(
        code="LUMORA-DOMAIN-LIFE-001",
        message=f"Cannot {operation} {aggregate} from state {state!r}",
        remediation=f"Perform {operation} only from one of: {', '.join(allowed_states)}.",
        context={
            "aggregate": aggregate,
            "state": state,
            "operation": operation,
            "allowed_states": allowed_states,
        },
    )


__all__ = [
    "AssociationDomainError",
    "CaptureDomainError",
    "DomainError",
    "DomainInvariantError",
    "InvalidStateTransitionError",
    "InvariantViolationError",
    "ReplayDomainError",
    "ReportDomainError",
    "StateTransitionError",
    "domain_invariant",
    "invalid_transition",
]
