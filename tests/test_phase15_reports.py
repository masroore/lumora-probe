"""Phase 15 report assembly, rendering, and async progress tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from lumora_probe.reports.contracts import ReportFormat
from lumora_probe.reports.service import ReportService

pytestmark = pytest.mark.component


def _write_capture(tmp_path: Path) -> Path:
    capture = tmp_path / "capture-15"
    (capture / "analysis").mkdir(parents=True)
    (capture / "manifest.json").write_text(
        json.dumps(
            {
                "capture_id": "capture-15",
                "source": "live",
                "source_capture_id": "source-1",
                "fidelity": "objects",
                "created_at": "2026-07-30T10:00:00+00:00",
                "completed_at": "2026-07-30T10:00:05+00:00",
                "partial": True,
                "promoted_from_buffer": True,
                "client_asserted_event_count": 1,
                "source_aggregate_ids": ["association-b", "association-a"],
                "objects": [{"digest": "a" * 64}],
            }
        ),
        encoding="utf-8",
    )
    events = [
        {
            "event_id": "event-2",
            "event_name": "ImageDecoded",
            "sequence": 2,
            "aggregate_id": "instance-1",
            "origin": "observed",
            "payload": {"duration_ns": 2_000_000, "frame_count": 2},
        },
        {
            "event_id": "event-1",
            "event_name": "WarningRaised",
            "sequence": 1,
            "aggregate_id": "association-1",
            "origin": "observed",
            "payload": {
                "code": "LP-NEG-001",
                "condition_name": "Association rejected",
                "message": "Peer rejected the association.",
                "source_event_id": "event-rejected",
                "source_sequence": 0,
                "details": {"reason": "temporary"},
            },
        },
        {
            "event_id": "event-client",
            "event_name": "WarningRaised",
            "sequence": 3,
            "aggregate_id": "association-1",
            "origin": "client-asserted",
            "payload": {"code": "CLIENT-ONLY", "message": "Do not include me."},
        },
    ]
    (capture / "events.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )
    (capture / "analysis" / "findings.json").write_text(
        json.dumps(
            {
                "format_version": 1,
                "rule_set_version": "bundled-v1",
                "findings": [
                    {
                        "rule_id": "LP-RULE-NEG-001",
                        "rule_version": "1",
                        "rule_set_version": "bundled-v1",
                        "confidence": "certain",
                        "cited_sequences": [1],
                        "explanation": "Negotiation was rejected by the peer.",
                        "next_steps": ["Compare peer negotiation settings"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return capture


@pytest.mark.asyncio
async def test_report_content_assembles_evidence_and_is_deterministic(tmp_path: Path) -> None:
    _write_capture(tmp_path)
    service = ReportService(tmp_path)

    first = await service.build("capture-15")
    second = await service.build("capture-15")

    assert first is not None
    assert second is not None
    assert first == second
    assert first.rule_set_version == "bundled-v1"
    assert first.conditions[0].code == "LP-NEG-001"
    assert first.conditions[0].source_sequence == 0
    assert first.findings[0].cited_sequences == (1,)
    assert first.timings[0].total_duration_ns == 2_000_000
    assert first.provenance.source_capture_id == "source-1"
    assert first.provenance.source_aggregate_ids == ("association-a", "association-b")
    assert first.provenance.object_count == 1
    assert "CLIENT-ONLY" not in json.dumps(first.model_dump(mode="json"))


@pytest.mark.asyncio
async def test_html_and_markdown_render_from_the_same_report_contract(tmp_path: Path) -> None:
    _write_capture(tmp_path)
    service = ReportService(tmp_path)

    html = await service.render_html("capture-15")
    markdown = await service.render_markdown("capture-15")

    assert html is not None and markdown is not None
    assert '<html lang="en">' in html
    assert "LP-NEG-001" in html
    assert "2,000,000" not in html
    assert "2_000_000" not in html
    assert "## Conditions" in markdown
    assert "LP-RULE-NEG-001 v1 — certain" in markdown
    assert "2,000,000" not in markdown
    assert "2_000_000" not in markdown


@pytest.mark.asyncio
async def test_generate_reports_progress_and_returns_artifact_metadata(tmp_path: Path) -> None:
    _write_capture(tmp_path)
    service = ReportService(tmp_path)
    progress: list[dict[str, Any]] = []

    artifact = await service.generate(
        "capture-15",
        format=ReportFormat.HTML,
        progress_callback=progress.append,
    )

    assert artifact is not None
    assert artifact.format is ReportFormat.HTML
    assert artifact.media_type.startswith("text/html")
    assert artifact.content == artifact.body
    assert [item["stage"] for item in progress] == [
        "reading",
        "reading",
        "assembled",
        "rendering",
        "completed",
    ]
    assert progress[-1]["fraction"] == 1.0


@pytest.mark.asyncio
async def test_report_generation_does_not_run_when_capture_event_log_is_missing(
    tmp_path: Path,
) -> None:
    service = ReportService(tmp_path)

    assert await service.generate("missing", format="markdown") is None
