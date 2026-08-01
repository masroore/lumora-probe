# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Asynchronous, deterministic report assembly and Jinja rendering."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from .contracts import (
    CaptureDecodeTiming,
    CaptureSummaryReport,
    ProgressCallback,
    RenderedReport,
    ReportCondition,
    ReportContent,
    ReportFinding,
    ReportFormat,
    ReportProgress,
    ReportProvenance,
)
from .repository import CaptureEvidence, ReportRepository

_REPORT_VERSION = 1
_UNKNOWN_RULE_SET = "unknown"
_MEDIA_TYPES = {
    ReportFormat.HTML: "text/html; charset=utf-8",
    ReportFormat.MARKDOWN: "text/markdown; charset=utf-8",
    ReportFormat.JSON: "application/json",
}


class ReportService:
    """Build reports from capture evidence without running analysis rules."""

    def __init__(self, captures_root: Path, *, template_root: Path | None = None) -> None:
        self._repository = ReportRepository(captures_root)
        self._template_root = (template_root or Path(__file__).with_name("templates")).resolve()

    async def build(
        self,
        capture_id: str,
        *,
        rule_set_version: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ReportContent | None:
        """Assemble deterministic content from the event log, manifest, and findings file."""
        await self._progress(progress_callback, "reading", 1, "Reading capture evidence")
        evidence = await asyncio.to_thread(self._repository.read, capture_id)
        if evidence is None:
            return None
        await self._progress(progress_callback, "reading", 2, "Capture evidence loaded")
        content = await asyncio.to_thread(
            self._assemble,
            evidence,
            rule_set_version,
        )
        await self._progress(progress_callback, "assembled", 3, "Report content assembled")
        return content

    async def generate(
        self,
        capture_id: str,
        *,
        format: ReportFormat | str = ReportFormat.HTML,
        rule_set_version: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> RenderedReport | None:
        """Generate one rendered artifact, suitable for an async background worker."""
        report_format = _normalize_format(format)
        content = await self.build(
            capture_id,
            rule_set_version=rule_set_version,
            progress_callback=progress_callback,
        )
        if content is None:
            return None
        await self._progress(progress_callback, "rendering", 4, "Rendering report")
        body = await asyncio.to_thread(self._render, content, report_format)
        await self._progress(progress_callback, "completed", 5, "Report generated")
        return RenderedReport(
            report_version=_REPORT_VERSION,
            capture_id=content.capture_id,
            format=report_format,
            media_type=_MEDIA_TYPES[report_format],
            body=body,
            report=content,
        )

    async def render(
        self,
        capture_id: str,
        *,
        format: ReportFormat | str = ReportFormat.HTML,
        rule_set_version: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> str | None:
        """Return rendered text for callers that do not need artifact metadata."""
        artifact = await self.generate(
            capture_id,
            format=format,
            rule_set_version=rule_set_version,
            progress_callback=progress_callback,
        )
        return None if artifact is None else artifact.body

    async def render_html(
        self,
        capture_id: str,
        *,
        rule_set_version: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> str | None:
        """Render an HTML report."""
        return await self.render(
            capture_id,
            format=ReportFormat.HTML,
            rule_set_version=rule_set_version,
            progress_callback=progress_callback,
        )

    async def render_markdown(
        self,
        capture_id: str,
        *,
        rule_set_version: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> str | None:
        """Render a Markdown report."""
        return await self.render(
            capture_id,
            format=ReportFormat.MARKDOWN,
            rule_set_version=rule_set_version,
            progress_callback=progress_callback,
        )

    async def _progress(
        self,
        callback: ProgressCallback | None,
        stage: str,
        completed: int,
        message: str,
    ) -> None:
        if callback is None:
            return
        progress = ReportProgress(
            stage=stage,
            completed=completed,
            total=5,
            fraction=completed / 5,
            message=message,
        ).model_dump(mode="json")
        result = callback(progress)
        if inspect.isawaitable(result):
            await result

    @staticmethod
    def _assemble(
        evidence: CaptureEvidence,
        requested_rule_set_version: str | None,
    ) -> ReportContent:
        rule_set_version = _select_rule_set_version(evidence, requested_rule_set_version)
        event_sequences = {
            event["sequence"]
            for event in evidence.events
            if type(event.get("sequence")) is int and event["sequence"] >= 0
        }
        findings = _findings(evidence.findings, rule_set_version, event_sequences)
        return ReportContent(
            report_version=_REPORT_VERSION,
            capture_id=evidence.capture_id,
            generated_from=str(evidence.capture_path),
            rule_set_version=rule_set_version,
            conditions=_conditions(evidence.events),
            findings=findings,
            timings=_decode_timings(evidence.events),
            provenance=_provenance(evidence.manifest),
        )

    def _render(self, report: ReportContent, report_format: ReportFormat) -> str:
        if report_format is ReportFormat.JSON:
            return json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        environment = Environment(
            loader=FileSystemLoader(str(self._template_root)),
            autoescape=report_format is ReportFormat.HTML,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        template_name = "report.html.j2" if report_format is ReportFormat.HTML else "report.md.j2"
        template = environment.get_template(template_name)
        return template.render(report=report.model_dump(mode="json"))


class CaptureSummaryService:
    """Build the Phase 13 JSON capture summary from the same evidence repository."""

    def __init__(self, captures_root: Path) -> None:
        self._repository = ReportRepository(captures_root)

    async def build(self, capture_id: str) -> CaptureSummaryReport | None:
        """Read events.jsonl off-loop and aggregate ImageDecoded timing per instance."""
        evidence = await asyncio.to_thread(self._repository.read, capture_id)
        if evidence is None:
            return None
        return CaptureSummaryReport(
            capture_id=capture_id,
            generated_from=str(evidence.capture_path),
            decode_timings=_decode_timings(evidence.events),
        )


# Descriptive aliases keep composition code independent of the implementation name.
ReportGenerationService = ReportService


def _normalize_format(value: ReportFormat | str) -> ReportFormat:
    if isinstance(value, ReportFormat):
        return value
    try:
        return ReportFormat(value.strip().lower())
    except (AttributeError, ValueError) as exc:
        raise ValueError("format must be html, markdown, or json") from exc


def _select_rule_set_version(
    evidence: CaptureEvidence,
    requested: str | None,
) -> str:
    if requested is not None and (type(requested) is not str or not requested.strip()):
        raise ValueError("rule_set_version must be a non-empty string")
    requested_value = requested.strip() if isinstance(requested, str) else None
    versions = {
        value.get("rule_set_version")
        for value in evidence.findings
        if isinstance(value.get("rule_set_version"), str) and value["rule_set_version"].strip()
    }
    if evidence.findings_rule_set_version:
        versions.add(evidence.findings_rule_set_version)
    normalized_versions = {value.strip() for value in versions if isinstance(value, str)}
    if len(normalized_versions) > 1:
        raise ValueError("findings contain multiple rule-set versions")
    discovered = next(iter(normalized_versions), _UNKNOWN_RULE_SET)
    if (
        requested_value is not None
        and discovered != _UNKNOWN_RULE_SET
        and requested_value != discovered
    ):
        raise ValueError("requested rule-set version does not match persisted findings")
    return requested_value or discovered


def _findings(
    values: tuple[Mapping[str, Any], ...],
    rule_set_version: str,
    event_sequences: set[int],
) -> tuple[ReportFinding, ...]:
    result: list[ReportFinding] = []
    for value in values:
        document = dict(value)
        document.setdefault("rule_set_version", rule_set_version)
        finding = ReportFinding.model_validate(document)
        if any(sequence not in event_sequences for sequence in finding.cited_sequences):
            raise ValueError(f"finding {finding.rule_id} cites an unknown event sequence")
        result.append(finding)
    return tuple(
        sorted(
            result,
            key=lambda finding: (
                finding.rule_id,
                finding.rule_version,
                finding.cited_sequences,
                finding.explanation,
            ),
        )
    )


def _conditions(events: tuple[Mapping[str, Any], ...]) -> tuple[ReportCondition, ...]:
    conditions: list[ReportCondition] = []
    for event in events:
        if event.get("origin") == "client-asserted":
            continue
        if event.get("event_name") not in {"WarningRaised", "ErrorRaised"}:
            continue
        payload = event.get("payload")
        payload_mapping = payload if isinstance(payload, Mapping) else {}  # pyright: ignore[reportUnknownVariableType]
        condition_id = payload_mapping.get("condition_code") or payload_mapping.get("code")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not isinstance(condition_id, str) or not condition_id.strip():
            condition_id = "unknown-condition"
        details = payload_mapping.get("details")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not isinstance(details, Mapping):
            details = {  # pyright: ignore[reportUnknownVariableType]
                key: value
                for key, value in payload_mapping.items()  # pyright: ignore[reportUnknownVariableType]
                if key
                not in {
                    "condition_code",
                    "code",
                    "condition_name",
                    "message",
                    "reason",
                    "source_event_id",
                    "source_sequence",
                }
            }
        sequence = payload_mapping.get("source_sequence", event.get("sequence"))  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if type(sequence) is not int or sequence < 0:  # pyright: ignore[reportUnknownArgumentType]
            sequence = None
        event_id = event.get("event_id")
        source_event_id = payload_mapping.get("source_event_id") or event_id  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not isinstance(source_event_id, str) or not source_event_id.strip():
            source_event_id = f"sequence-{sequence}" if sequence is not None else "unknown-event"
        aggregate_id = event.get("aggregate_id")
        if not isinstance(aggregate_id, str) or not aggregate_id.strip():
            aggregate_id = "unknown"
        message = payload_mapping.get("message") or payload_mapping.get("reason")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not isinstance(message, str) or not message.strip():
            message = str(condition_id)
        condition_name = payload_mapping.get("condition_name")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not isinstance(condition_name, str) or not condition_name.strip():
            condition_name = str(condition_id)
        conditions.append(
            ReportCondition(
                condition_id=str(condition_id),
                condition_name=condition_name,
                event_name=str(event.get("event_name")),
                source_event_id=source_event_id,
                source_sequence=sequence,
                aggregate_id=aggregate_id,
                message=message,
                details=dict(details),  # pyright: ignore[reportUnknownArgumentType]
            )
        )
    return tuple(
        sorted(
            conditions,
            key=lambda condition: (
                condition.source_sequence is None,
                condition.source_sequence if condition.source_sequence is not None else 0,
                condition.condition_id,
                condition.source_event_id,
            ),
        )
    )


def _decode_timings(events: tuple[Mapping[str, Any], ...]) -> tuple[CaptureDecodeTiming, ...]:
    timings: dict[str, dict[str, int]] = {}
    for event in events:
        if event.get("event_name") != "ImageDecoded" or event.get("origin") == "client-asserted":
            continue
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            continue
        duration_ns = payload.get("duration_ns", 0)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        frame_count = payload.get("frame_count", 1)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if type(duration_ns) is not int or duration_ns < 0:  # pyright: ignore[reportUnknownArgumentType]
            continue
        if type(frame_count) is not int or frame_count < 1:  # pyright: ignore[reportUnknownArgumentType]
            continue
        aggregate_id = event.get("aggregate_id") or "unknown"
        if not isinstance(aggregate_id, str):
            aggregate_id = str(aggregate_id)
        entry = timings.setdefault(aggregate_id, {"frame_count": 0, "total": 0, "max": 0})
        entry["frame_count"] += frame_count
        entry["total"] += duration_ns
        entry["max"] = max(entry["max"], duration_ns)
    return tuple(
        CaptureDecodeTiming(
            instance_id=instance_id,
            frame_count=entry["frame_count"],
            total_duration_ns=entry["total"],
            max_duration_ns=entry["max"],
        )
        for instance_id, entry in sorted(timings.items())
    )


def _provenance(manifest: Mapping[str, Any]) -> ReportProvenance:
    source_aggregate_ids = manifest.get("source_aggregate_ids", ())
    if not isinstance(source_aggregate_ids, (list, tuple)):
        source_aggregate_ids = ()
    return ReportProvenance(
        source=str(manifest.get("source") or "unknown"),
        source_capture_id=_optional_text(manifest.get("source_capture_id")),
        redaction_profile=_optional_text(manifest.get("redaction_profile")),
        fidelity=_optional_text(manifest.get("fidelity")),
        created_at=_optional_datetime(manifest.get("created_at")),
        completed_at=_optional_datetime(manifest.get("completed_at")),
        partial=bool(manifest.get("partial", False)),
        promoted_from_buffer=bool(manifest.get("promoted_from_buffer", False)),
        client_asserted_event_count=_non_negative_int(
            manifest.get("client_asserted_event_count", 0)
        ),
        source_aggregate_ids=tuple(sorted({str(value) for value in source_aggregate_ids})),  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
        object_count=len(manifest.get("objects", ()))
        if isinstance(manifest.get("objects"), list)
        else 0,
    )


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_datetime(value: object) -> Any:
    return value if isinstance(value, str) or value is None else None


def _non_negative_int(value: object) -> int:
    return value if type(value) is int and value >= 0 else 0


__all__: tuple[str, ...] = ()
