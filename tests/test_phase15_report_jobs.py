# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 15 background report generation tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from lumora_probe.core.operations import InMemoryJobRegistry, JobState
from lumora_probe.reports.contracts import ReportFormat
from lumora_probe.reports.jobs import ReportJobService
from lumora_probe.reports.service import CaptureSummaryService, ReportService
from lumora_probe.web.api import create_app
from tests.doubles.clock import ControllableClock
from tests.doubles.ids import SeededIdGenerator
from tests.test_phase15_reports import _write_capture


class Publisher:
    def __init__(self) -> None:
        self.events = []

    async def publish(self, event, *, capture_id=None):
        self.events.append(event)
        return event


@pytest.mark.asyncio
async def test_report_job_publishes_progress_and_generated_event(tmp_path: Path) -> None:
    _write_capture(tmp_path)
    publisher = Publisher()
    jobs = InMemoryJobRegistry(
        progress_publisher=publisher, concurrency_limits={"report-generation": 1}
    )
    service = ReportJobService(
        ReportService(tmp_path),
        jobs,
        tmp_path / "reports",
        publisher=publisher,
        clock=ControllableClock(datetime(2026, 7, 30, tzinfo=UTC)),
        id_generator=SeededIdGenerator(
            [
                "018f0c40-7d3d-7abc-8d2e-5b5a58fce0d0",
            ]
        ),
    )

    started = await service.start("capture-15", format=ReportFormat.MARKDOWN)
    assert started.state is JobState.RUNNING

    completed = await jobs.wait(started.operation_id)
    assert completed is not None
    assert completed.state is JobState.COMPLETED
    assert completed.outcome is not None
    artifact = await service.read_artifact(started.operation_id)
    assert artifact is not None
    assert "# Lumora Probe report" in artifact

    assert any(event.event_name == "ReportProgressed" for event in publisher.events)
    generated = [event for event in publisher.events if event.event_name == "ReportGenerated"]
    assert len(generated) == 1
    assert generated[0].origin.value == "observed"
    assert generated[0].payload["capture_id"] == "capture-15"


@pytest.mark.asyncio
async def test_report_job_failure_does_not_publish_generated_event(tmp_path: Path) -> None:
    publisher = Publisher()
    jobs = InMemoryJobRegistry(progress_publisher=publisher)
    service = ReportJobService(
        ReportService(tmp_path),
        jobs,
        tmp_path / "reports",
        publisher=publisher,
        clock=ControllableClock(datetime(2026, 7, 30, tzinfo=UTC)),
        id_generator=SeededIdGenerator(["018f0c40-7d3d-7abc-8d2e-5b5a58fce0d1"]),
    )

    started = await service.start("missing")
    completed = await jobs.wait(started.operation_id)

    assert completed is not None
    assert completed.state is JobState.FAILED
    assert await service.read_artifact(started.operation_id) is None
    assert not any(event.event_name == "ReportGenerated" for event in publisher.events)


@pytest.mark.asyncio
async def test_report_generation_route_returns_operation_id(tmp_path: Path) -> None:
    _write_capture(tmp_path)
    jobs = InMemoryJobRegistry()
    report_jobs = ReportJobService(ReportService(tmp_path), jobs, tmp_path / "reports")
    application = create_app(
        reports_provider=CaptureSummaryService(tmp_path),
        report_job_provider=report_jobs,
    )

    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.post("/api/v1/captures/capture-15/report?format=markdown")

    assert response.status_code == 202
    payload = response.json()
    assert payload["job_type"] == "report-generation"
    assert payload["parameters"]["format"] == "markdown"
    await jobs.wait(payload["operation_id"])
