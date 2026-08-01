# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Background report generation on the shared operation and event infrastructure."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Protocol

from lumora_probe.core.paths import assert_contained
from lumora_probe.shared.events import EventEnvelope, EventOrigin

from .contracts import ReportFormat
from .service import ReportService


class ReportJobContext(Protocol):
    operation_id: str

    async def report_progress(self, progress: Mapping[str, object]) -> None: ...


class ReportJobRecord(Protocol):
    operation_id: str
    job_type: str
    state: object
    parameters: dict[str, object]


class ReportJobRegistry(Protocol):
    async def start(
        self,
        job_type: str,
        worker: Callable[[ReportJobContext], Awaitable[str | None]],
        *,
        parameters: Mapping[str, object],
        progress_event_name: str,
    ) -> ReportJobRecord: ...


class ReportProgressPublisher(Protocol):
    async def publish(self, event: object, *, capture_id: str | None = None) -> object: ...


class ClockSource(Protocol):
    def now(self) -> datetime: ...

    def monotonic_ns(self) -> int: ...


class IdSource(Protocol):
    def new_id(self) -> str: ...


class ReportJobService:
    """Schedule, persist, and publish one report-generation operation."""

    def __init__(
        self,
        report_service: ReportService,
        jobs: ReportJobRegistry,
        reports_root: Path,
        *,
        publisher: ReportProgressPublisher | None = None,
        clock: ClockSource | None = None,
        id_generator: IdSource | None = None,
    ) -> None:
        self._service = report_service
        self._jobs = jobs
        self._reports_root = reports_root.expanduser().resolve()
        if publisher is not None and (clock is None or id_generator is None):
            raise ValueError("publisher requires injected clock and id_generator")
        self._publisher = publisher
        self._clock = clock
        self._id_generator = id_generator

    async def start(
        self,
        capture_id: str,
        *,
        format: ReportFormat | str = ReportFormat.HTML,
        rule_set_version: str | None = None,
    ) -> ReportJobRecord:
        """Return immediately with a job record; execution is never auto-resumed."""
        report_format = _normalize_format(format)
        parameters = {
            "capture_id": capture_id,
            "format": report_format.value,
            "rule_set_version": rule_set_version,
        }

        async def worker(context: ReportJobContext) -> str:
            artifact = await self._service.generate(
                capture_id,
                format=report_format,
                rule_set_version=rule_set_version,
                progress_callback=context.report_progress,
            )
            if artifact is None:
                raise ValueError(f"capture not found: {capture_id}")
            artifact_path = await asyncio.to_thread(
                self._persist, context.operation_id, report_format, artifact.body
            )
            await self._publish_generated(
                context.operation_id,
                capture_id,
                report_format,
                artifact.report.rule_set_version,
                artifact_path,
            )
            return str(artifact_path)

        return await self._jobs.start(
            "report-generation",
            worker,
            parameters=parameters,
            progress_event_name="ReportProgressed",
        )

    async def read_artifact(self, operation_id: str) -> str | None:
        """Read a completed report artifact without blocking the event loop."""
        path = self._artifact_path(operation_id)
        if not path.is_file():
            return None
        return await asyncio.to_thread(path.read_text, encoding="utf-8")

    def _persist(self, operation_id: str, report_format: ReportFormat, body: str) -> Path:
        self._reports_root.mkdir(parents=True, exist_ok=True)
        destination = self._artifact_path(operation_id, report_format)
        temporary = destination.with_name(f".{destination.name}.tmp")
        temporary.write_text(body, encoding="utf-8")
        os.replace(temporary, destination)
        return destination

    def _artifact_path(self, operation_id: str, report_format: ReportFormat | None = None) -> Path:
        if type(operation_id) is not str or not operation_id.strip():
            raise ValueError("operation_id must be a non-empty string")
        if report_format is None:
            candidates = tuple(self._reports_root.glob(f"{operation_id.strip()}.*"))
            return (
                candidates[0]
                if candidates
                else assert_contained(
                    self._reports_root / f"{operation_id.strip()}.html", self._reports_root
                )
            )
        return assert_contained(
            self._reports_root / f"{operation_id.strip()}.{report_format.value}",
            self._reports_root,
        )

    async def _publish_generated(
        self,
        operation_id: str,
        capture_id: str,
        report_format: ReportFormat,
        rule_set_version: str,
        artifact_path: Path,
    ) -> None:
        if self._publisher is None:
            return
        if self._clock is None or self._id_generator is None:
            raise RuntimeError("report event publishing requires injected clock and id_generator")
        event = EventEnvelope.create(
            event_name="ReportGenerated",
            event_version=1,
            correlation_id=operation_id,
            aggregate_type="Report",
            aggregate_id=operation_id,
            producer="report-job",
            payload={
                "report_id": operation_id,
                "capture_id": capture_id,
                "format": report_format.value,
                "rule_set_version": rule_set_version,
                "artifact_path": str(artifact_path),
            },
            origin=EventOrigin.OBSERVED,
            clock=self._clock,
            id_generator=self._id_generator,
        )
        await self._publisher.publish(event)


def _normalize_format(value: ReportFormat | str) -> ReportFormat:
    if isinstance(value, ReportFormat):
        return value
    try:
        normalized = value.strip().lower()
    except AttributeError as exc:
        raise ValueError("format must be html, markdown, or json") from exc
    try:
        return ReportFormat(normalized)
    except ValueError as exc:
        raise ValueError("format must be html, markdown, or json") from exc


__all__ = ["ReportJobService"]
