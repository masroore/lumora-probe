"""Stdout-only text and JSONL event logging for Sender Lite.

Mirrors ProbeLogger behavior. Do not refactor ProbeLogger into shared
infrastructure; this module duplicates the pattern so Sender Lite remains
self-contained.

PHI rule (section 14.3): never log Patient Name, Patient ID, accession
number, dates of birth, Study/Series descriptions, free-text dataset
values, or full dataset dumps. UIDs and source paths are allowed for
engineering correlation. Source paths may themselves contain sensitive
text.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Any, TextIO

_TEXT_LABELS = {
    "configuration_resolved": "Configuration resolved",
    "scan_started": "Scan started",
    "file_skipped": "File skipped",
    "catalog_conflict": "Catalog conflict",
    "scan_completed": "Scan completed",
    "study_started": "Study started",
    "association_accepted": "Association accepted",
    "association_rejected": "Association rejected",
    "association_aborted": "Association aborted",
    "presentation_context_rejected": "Presentation context rejected",
    "instance_sent": "Instance sent",
    "instance_warning": "Instance warning",
    "instance_failed": "Instance failed",
    "study_completed": "Study completed",
    "study_delay_started": "Study delay started",
    "echo_completed": "Echo completed",
    "cancellation_requested": "Cancellation requested",
    "run_completed": "Run completed",
    "run_failed": "Run failed",
}


class SenderLogger:
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
