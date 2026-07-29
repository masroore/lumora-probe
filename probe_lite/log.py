"""Stdout-only text and JSONL event logging."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Any, TextIO

_TEXT_LABELS = {
    "startup": "Startup",
    "association_requested": "Association requested",
    "association_accepted": "Association accepted",
    "association_rejected": "Association rejected",
    "association_released": "Association released",
    "association_aborted": "Association aborted",
    "instance_received": "Instance received",
    "instance_store_failed": "Instance store failed",
    "c_echo_received": "C-ECHO received",
    "shutdown": "Shutdown",
}


class ProbeLogger:
    """Small logger with no file handlers or global logging configuration."""

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
        label = _TEXT_LABELS.get(event, event.replace("_", " ").title())
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
