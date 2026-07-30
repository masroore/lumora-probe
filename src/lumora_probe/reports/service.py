"""Capture summary report builder reading events off-loop."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .contracts import CaptureDecodeTiming, CaptureSummaryReport


class CaptureSummaryService:
    """Build a structured capture summary from the capture directory's event log."""

    def __init__(self, captures_root: Path) -> None:
        self._captures_root = captures_root.expanduser().resolve()

    async def build(self, capture_id: str) -> CaptureSummaryReport | None:
        """Read events.jsonl off-loop and aggregate ImageDecoded timing per instance."""
        capture_dir = self._captures_root / capture_id
        events_path = capture_dir / "events.jsonl"
        if not events_path.is_file():
            return None
        lines = await asyncio.to_thread(events_path.read_text)
        timings: dict[str, dict[str, int]] = {}
        for line in lines.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                envelope = json.loads(line)
            except json.JSONDecodeError:
                continue
            if envelope.get("event_name") != "ImageDecoded":
                continue
            # Client-asserted events are quarantined from analysis (ADR-0016)
            if envelope.get("origin") == "client-asserted":
                continue
            payload = envelope.get("payload", {})
            aggregate_id = envelope.get("aggregate_id") or "unknown"
            duration_ns = payload.get("duration_ns", 0)
            frame_count = payload.get("frame_count", 1)
            if aggregate_id not in timings:
                timings[aggregate_id] = {"frame_count": 0, "total": 0, "max": 0}
            entry = timings[aggregate_id]
            entry["frame_count"] += frame_count
            entry["total"] += duration_ns
            entry["max"] = max(entry["max"], duration_ns)
        decode_timings = tuple(
            CaptureDecodeTiming(
                instance_id=instance_id,
                frame_count=entry["frame_count"],
                total_duration_ns=entry["total"],
                max_duration_ns=entry["max"],
            )
            for instance_id, entry in sorted(timings.items())
        )
        return CaptureSummaryReport(
            capture_id=capture_id,
            generated_from=str(capture_dir),
            decode_timings=decode_timings,
        )


__all__: tuple[str, ...] = ()
