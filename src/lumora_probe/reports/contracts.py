"""Deterministic boundary models for rendered investigation reports."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReportFormat(StrEnum):
    """Supported report representations."""

    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"


class CaptureDecodeTiming(BaseModel):
    """Aggregated decode timing evidence for one instance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    instance_id: str
    frame_count: int = Field(ge=0)
    total_duration_ns: int = Field(ge=0)
    max_duration_ns: int = Field(ge=0)


class CaptureSummaryReport(BaseModel):
    """Structured JSON capture summary including decode timing evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_version: int = 1
    capture_id: str
    generated_from: str
    decode_timings: tuple[CaptureDecodeTiming, ...]


class ReportCondition(BaseModel):
    """Observed condition included in a report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    condition_id: str
    condition_name: str
    event_name: str
    source_event_id: str
    source_sequence: int | None = Field(default=None, ge=0)
    aggregate_id: str
    message: str
    details: Mapping[str, Any] = Field(default_factory=dict)

    @property
    def code(self) -> str:
        """Return the stable condition identifier."""
        return self.condition_id

    @field_validator(
        "condition_id",
        "condition_name",
        "event_name",
        "source_event_id",
        "aggregate_id",
        "message",
    )
    @classmethod
    def validate_text(cls, value: str) -> str:
        if type(value) is not str or not value.strip():
            raise ValueError("report condition text fields must be non-empty strings")
        return value.strip()


class ReportFinding(BaseModel):
    """Versioned, evidence-linked analysis finding included in a report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    rule_version: str
    rule_set_version: str
    confidence: str
    cited_sequences: tuple[int, ...]
    explanation: str
    next_steps: tuple[str, ...]

    @field_validator("rule_id", "rule_version", "rule_set_version", "confidence", "explanation")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if type(value) is not str or not value.strip():
            raise ValueError("report finding text fields must be non-empty strings")
        return value.strip()

    @field_validator("cited_sequences")
    @classmethod
    def validate_sequences(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if value != tuple(sorted(set(value))) or any(
            type(sequence) is not int or sequence < 0 for sequence in value
        ):
            raise ValueError("cited_sequences must be unique and sorted non-negative integers")
        return value

    @field_validator("next_steps")
    @classmethod
    def validate_next_steps(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(type(step) is not str or not step.strip() for step in value):
            raise ValueError("next_steps must contain non-empty strings")
        return tuple(step.strip() for step in value)


class ReportProvenance(BaseModel):
    """Capture provenance needed to interpret a report's evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    source_capture_id: str | None = None
    redaction_profile: str | None = None
    fidelity: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    partial: bool = False
    promoted_from_buffer: bool = False
    client_asserted_event_count: int = Field(default=0, ge=0)
    source_aggregate_ids: tuple[str, ...] = ()
    object_count: int = Field(default=0, ge=0)

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        if type(value) is not str or not value.strip():
            raise ValueError("provenance source must be a non-empty string")
        return value.strip()


class ReportContent(BaseModel):
    """Complete deterministic report model shared by HTML and Markdown renderers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_version: int = 1
    capture_id: str
    generated_from: str
    rule_set_version: str
    conditions: tuple[ReportCondition, ...] = ()
    findings: tuple[ReportFinding, ...] = ()
    timings: tuple[CaptureDecodeTiming, ...] = ()
    provenance: ReportProvenance

    @property
    def decode_timings(self) -> tuple[CaptureDecodeTiming, ...]:
        """Compatibility view for callers of the Phase 13 summary contract."""
        return self.timings


class RenderedReport(BaseModel):
    """Rendered report artifact returned by the background-friendly API."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_version: int = 1
    capture_id: str
    format: ReportFormat
    media_type: str
    body: str
    report: ReportContent

    @property
    def content(self) -> str:
        """Return rendered text using the name commonly used by exporters."""
        return self.body


class ReportProgress(BaseModel):
    """Serializable progress checkpoint for a report generation job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: str
    completed: int = Field(ge=0)
    total: int = Field(gt=0)
    fraction: float = Field(ge=0, le=1)
    message: str


type ProgressCallback = Callable[[Mapping[str, Any]], Awaitable[None] | None]


# Names used by integrations that prefer the shorter vocabulary.
ReportDocument = ReportContent
ReportOutput = RenderedReport
ReportTiming = CaptureDecodeTiming

__all__: tuple[str, ...] = ()
