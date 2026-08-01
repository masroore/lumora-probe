# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Structured logging setup with correlation context and sensitive-value redaction."""

from __future__ import annotations

import logging
import sys
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from typing import Any, cast
from uuid import uuid4

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, unbind_contextvars

_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "authorization",
        "api_key",
        "access_key",
        "private_key",
        "credential",
        "certificate",
        "client_secret",
        "refresh_token",
    }
)
_EVENT_MIRROR_KEYS = frozenset({"event", "envelope", "payload", "event_payload", "event_json"})


def _redact(value: object) -> object:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {
            str(key): "[REDACTED]" if str(key).lower() in _SENSITIVE_KEYS else _redact(item)
            for key, item in mapping.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in cast(list[object], value)]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in cast(tuple[object, ...], value))
    return value


def redact_sensitive(
    _: Any, __: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Structlog processor that redacts sensitive keys recursively."""

    return cast(structlog.types.EventDict, _redact(event_dict))


def configure_logging(*, json_logs: bool = False, level: int = logging.INFO) -> None:
    """Configure stdlib and structlog exactly once for the running process."""

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            timestamper,
            redact_sensitive,
            renderer,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    logging.basicConfig(level=level, stream=sys.stderr, force=True)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def log_operational(
    logger: structlog.stdlib.BoundLogger,
    message: str,
    *,
    level: str = "info",
    **fields: Any,
) -> None:
    """Log an operational fact while rejecting full domain-event mirrors."""
    mirrored = sorted(_EVENT_MIRROR_KEYS.intersection(fields))
    if mirrored:
        raise ValueError(f"operational logs must not mirror event fields: {', '.join(mirrored)}")
    if level not in {"debug", "info", "warning", "error", "critical"}:
        raise ValueError(f"unsupported operational log level: {level}")
    getattr(logger, level)(message, **fields)


def new_correlation_id() -> str:
    """Generate an opaque correlation ID; Phase 05 supplies the injectable ID protocol."""

    return str(uuid4())


@contextmanager
def correlation_context(correlation_id: str | None = None, **values: Any) -> Generator[str]:
    """Bind a correlation ID and optional fields for the current async/thread context."""

    identifier = correlation_id or new_correlation_id()
    bind_contextvars(correlation_id=identifier, **values)
    try:
        yield identifier
    finally:
        unbind_contextvars("correlation_id", *values.keys())


def clear_correlation_context() -> None:
    clear_contextvars()
