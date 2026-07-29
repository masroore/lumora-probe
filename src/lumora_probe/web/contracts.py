"""Public contracts boundary for the ``web`` slice."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, Field

from lumora_probe.core.errors import LumoraError


class ErrorResponse(BaseModel):
    """Structured HTTP representation of a :class:`LumoraError`."""

    status: int = Field(ge=100, le=599)
    code: str
    message: str
    remediation: str
    context: dict[str, Any]
    correlation_id: str

    @classmethod
    def from_error(
        cls,
        error: LumoraError,
        *,
        correlation_id: str,
        status: int = 500,
    ) -> Self:
        """Build an HTTP error response from a core error."""

        return cls(status=status, correlation_id=correlation_id, **error.as_dict())


__all__: tuple[str, ...] = ()
