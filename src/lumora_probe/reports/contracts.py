"""Pydantic boundary models for capture summary reports."""

from __future__ import annotations

from pydantic import BaseModel


class CaptureDecodeTiming(BaseModel):
    """Aggregated decode timing evidence for one instance."""

    instance_id: str
    frame_count: int
    total_duration_ns: int
    max_duration_ns: int


class CaptureSummaryReport(BaseModel):
    """Structured JSON capture summary including decode timing evidence."""

    report_version: int = 1
    capture_id: str
    generated_from: str
    decode_timings: tuple[CaptureDecodeTiming, ...]


__all__: tuple[str, ...] = ()
