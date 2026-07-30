"""Read-only filesystem access for capture evidence used by reports."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CaptureEvidence:
    """Raw, immutable evidence inputs collected for one report."""

    capture_id: str
    capture_path: Path
    manifest: Mapping[str, Any]
    events: tuple[Mapping[str, Any], ...]
    findings: tuple[Mapping[str, Any], ...]
    findings_rule_set_version: str | None = None


class ReportRepository:
    """Read a capture manifest, event log, and regenerable analysis findings."""

    def __init__(self, captures_root: Path) -> None:
        self.captures_root = captures_root.expanduser().resolve()

    def read(self, capture_id: str) -> CaptureEvidence | None:
        """Return report inputs, or ``None`` when the capture event log is absent."""
        capture_path = self._capture_path(capture_id)
        events_path = capture_path / "events.jsonl"
        if not events_path.is_file():
            return None
        return CaptureEvidence(
            capture_id=capture_id,
            capture_path=capture_path,
            manifest=self._read_json(capture_path / "manifest.json"),
            events=self._read_jsonl(events_path),
            findings=self._read_findings(capture_path / "analysis" / "findings.json"),
            findings_rule_set_version=self._read_findings_rule_set_version(
                capture_path / "analysis" / "findings.json"
            ),
        )

    def _capture_path(self, capture_id: str) -> Path:
        if type(capture_id) is not str or not capture_id.strip():
            raise ValueError("capture_id must be a non-empty string")
        candidate = (self.captures_root / capture_id.strip()).resolve()
        try:
            candidate.relative_to(self.captures_root)
        except ValueError as exc:
            raise ValueError("capture_id must identify a child of captures_root") from exc
        return candidate

    @staticmethod
    def _read_json(path: Path) -> Mapping[str, Any]:
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _read_jsonl(path: Path) -> tuple[Mapping[str, Any], ...]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return ()
        events: list[Mapping[str, Any]] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(value)
        return tuple(sorted(events, key=_event_sort_key))

    @staticmethod
    def _read_findings(path: Path) -> tuple[Mapping[str, Any], ...]:
        document = ReportRepository._read_json(path)
        values = document.get("findings", ())
        if not isinstance(values, list):
            return ()
        return tuple(value for value in values if isinstance(value, dict))

    @staticmethod
    def _read_findings_rule_set_version(path: Path) -> str | None:
        value = ReportRepository._read_json(path).get("rule_set_version")
        return value.strip() if isinstance(value, str) and value.strip() else None


# Explicit names make the repository boundary easy to discover for composition code.
CaptureReportRepository = ReportRepository


def _event_sort_key(event: Mapping[str, Any]) -> tuple[int, str, str]:
    sequence = event.get("sequence")
    normalized_sequence = sequence if type(sequence) is int and sequence >= 0 else 2**63 - 1
    return normalized_sequence, str(event.get("event_id", "")), str(event.get("event_name", ""))


__all__: tuple[str, ...] = ()
