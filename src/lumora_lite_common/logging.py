"""Shared stdout-only event logger for the Lumora Lite tools.

`EventLogger` holds the text/JSONL rendering engine that `ProbeLogger` and
`SenderLogger` previously duplicated. A subclass overrides the class-level
`TEXT_LABELS` map (event name -> human label) and nothing else; all behaviour
lives here.

This is the one place in the shared package that uses inheritance, because the
logger has genuine shared state (``log_format``, ``stream``) plus shared methods
and a single point of real polymorphism (the label map). Everything else in the
package is plain functions. See ADR-0028.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Any, ClassVar, TextIO


class EventLogger:
    """Stdout-only text/JSONL event logger with no global logging state.

    Subclasses set ``TEXT_LABELS`` to map event names to human-readable labels
    for text mode. Unknown events fall back to a title-cased form of the name.
    """

    #: Override in subclasses: event name -> human label for text mode.
    TEXT_LABELS: ClassVar[dict[str, str]] = {}

    def __init__(self, log_format: str = "text", stream: TextIO | None = None) -> None:
        if log_format not in {"text", "json"}:
            raise ValueError("log_format must be text or json")
        self.log_format = log_format
        self.stream = stream or sys.stdout

    @staticmethod
    def _timestamp() -> datetime:
        return datetime.now(UTC)

    def event(self, event: str, level: str = "INFO", **fields: Any) -> None:
        timestamp = self._timestamp()
        if self.log_format == "json":
            payload = {
                "timestamp": timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "level": level,
                "event": event,
                **fields,
            }
            print(
                json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":")),
                file=self.stream,
                flush=True,
            )
            return

        local_time = timestamp.astimezone().strftime("%H:%M:%S.%f")[:-3]
        label = self.TEXT_LABELS.get(event, event.replace("_", " ").title())
        details = " ".join(f"{key.upper()}={_text_value(value)}" for key, value in fields.items())
        suffix = f": {details}" if details else ""
        print(f"{local_time} [{level}] {label}{suffix}", file=self.stream, flush=True)

    def info(self, event: str, **fields: Any) -> None:
        self.event(event, "INFO", **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self.event(event, "WARNING", **fields)

    def error(self, event: str, **fields: Any) -> None:
        self.event(event, "ERROR", **fields)


def _text_value(value: Any) -> str:
    if isinstance(value, (list, tuple, set, frozenset)):
        return ",".join(str(item) for item in value)
    return str(value).replace("\n", "\\n")
