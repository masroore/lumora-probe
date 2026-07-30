"""Filesystem persistence for regenerable capture analysis output."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path

from .domain import Finding, FindingConfidence

ANALYSIS_DIRECTORY = "analysis"
FINDINGS_FILENAME = "findings.json"


class AnalysisRepository:
    """Persist findings beneath one capture without touching captured evidence files."""

    def __init__(self, capture_path: Path) -> None:
        self.capture_path = capture_path.expanduser().resolve()
        self.analysis_path = self.capture_path / ANALYSIS_DIRECTORY
        self.findings_path = self.analysis_path / FINDINGS_FILENAME

    def write_findings(self, findings: Iterable[Finding], *, rule_set_version: str) -> Path:
        """Atomically replace regenerable findings for the configured capture."""
        if type(rule_set_version) is not str or not rule_set_version.strip():
            raise ValueError("rule_set_version must be a non-empty string")
        values = tuple(findings)
        if any(type(finding) is not Finding for finding in values):
            raise TypeError("findings must contain Finding values")
        document = {
            "format_version": 1,
            "rule_set_version": rule_set_version.strip(),
            "findings": [finding.as_dict() for finding in values],
        }
        raw = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
        self.analysis_path.mkdir(parents=True, exist_ok=True)
        temporary = self.findings_path.with_name(f".{self.findings_path.name}.tmp")
        with temporary.open("wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.findings_path)
        return self.findings_path

    def read_findings(self) -> tuple[Finding, ...]:
        """Read and validate findings from the capture's analysis directory."""
        if not self.findings_path.is_file():
            return ()
        document = json.loads(self.findings_path.read_text(encoding="utf-8"))
        values = document.get("findings", [])
        return tuple(
            Finding(
                rule_id=value["rule_id"],
                rule_version=value["rule_version"],
                confidence=FindingConfidence(value["confidence"]),
                cited_sequences=tuple(value["cited_sequences"]),
                explanation=value["explanation"],
                next_steps=tuple(value["next_steps"]),
            )
            for value in values
        )

    def delete_findings(self) -> None:
        """Delete only regenerable analysis output, leaving events and objects untouched."""
        if self.findings_path.exists():
            self.findings_path.unlink()
        if self.analysis_path.is_dir() and not any(self.analysis_path.iterdir()):
            self.analysis_path.rmdir()


__all__: tuple[str, ...] = ()
