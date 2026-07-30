"""Phase 13 capture summary report and decode timing tests."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from lumora_probe.reports.contracts import CaptureSummaryReport
from lumora_probe.reports.service import CaptureSummaryService
from lumora_probe.web.api import create_app

pytestmark = pytest.mark.component


def _write_events(capture_dir: Path, events: list[dict]) -> None:
    capture_dir.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(json.dumps(event) for event in events)
    (capture_dir / "events.jsonl").write_text(lines + "\n")


def _image_decoded_event(aggregate_id: str, duration_ns: int, frame_count: int = 1) -> dict:
    return {
        "event_name": "ImageDecoded",
        "event_version": 1,
        "aggregate_id": aggregate_id,
        "origin": "observed",
        "payload": {"duration_ns": duration_ns, "frame_count": frame_count},
    }


@pytest.mark.asyncio
async def test_capture_summary_aggregates_decode_timings(tmp_path: Path) -> None:
    capture_dir = tmp_path / "capture-1"
    _write_events(
        capture_dir,
        [
            _image_decoded_event("instance-a", 1_000_000),
            _image_decoded_event("instance-a", 2_000_000),
            _image_decoded_event("instance-b", 500_000),
        ],
    )
    service = CaptureSummaryService(tmp_path)

    report = await service.build("capture-1")

    assert report is not None
    assert isinstance(report, CaptureSummaryReport)
    assert report.capture_id == "capture-1"
    assert report.report_version == 1
    timings = {t.instance_id: t for t in report.decode_timings}
    assert timings["instance-a"].total_duration_ns == 3_000_000
    assert timings["instance-a"].max_duration_ns == 2_000_000
    assert timings["instance-a"].frame_count == 2
    assert timings["instance-b"].total_duration_ns == 500_000


@pytest.mark.asyncio
async def test_client_asserted_events_excluded_from_report(tmp_path: Path) -> None:
    capture_dir = tmp_path / "capture-1"
    observed = _image_decoded_event("instance-a", 1_000_000)
    client_asserted = _image_decoded_event("instance-a", 9_999_999)
    client_asserted["origin"] = "client-asserted"
    _write_events(capture_dir, [observed, client_asserted])
    service = CaptureSummaryService(tmp_path)

    report = await service.build("capture-1")

    assert report is not None
    timings = {t.instance_id: t for t in report.decode_timings}
    assert timings["instance-a"].total_duration_ns == 1_000_000


@pytest.mark.asyncio
async def test_missing_capture_returns_none(tmp_path: Path) -> None:
    service = CaptureSummaryService(tmp_path)
    report = await service.build("nonexistent")
    assert report is None


@pytest.mark.asyncio
async def test_decode_duration_appears_in_exported_report(tmp_path: Path) -> None:
    """E2E: decode duration appears in a capture report over HTTP."""
    capture_dir = tmp_path / "capture-e2e"
    _write_events(
        capture_dir,
        [
            _image_decoded_event("sop-instance-1", 4_200_000, frame_count=3),
        ],
    )
    service = CaptureSummaryService(tmp_path)
    application = create_app(reports_provider=service)
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/api/v1/captures/capture-e2e/report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["report_version"] == 1
    assert payload["capture_id"] == "capture-e2e"
    timings = payload["decode_timings"]
    assert len(timings) == 1
    assert timings[0]["instance_id"] == "sop-instance-1"
    assert timings[0]["total_duration_ns"] == 4_200_000
    assert timings[0]["max_duration_ns"] == 4_200_000
    assert timings[0]["frame_count"] == 3


@pytest.mark.asyncio
async def test_report_endpoint_404_for_missing_capture(tmp_path: Path) -> None:
    service = CaptureSummaryService(tmp_path)
    application = create_app(reports_provider=service)
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/api/v1/captures/nonexistent/report")

    assert response.status_code == 404
