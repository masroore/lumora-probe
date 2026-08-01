# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Phase 12 golden capture and replay regression tests."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from lumora_probe.captures.format import CapturePackage, unpack_capture
from lumora_probe.replay.service import EventReplayService
from lumora_probe.shared.events import EventEnvelope
from tests.doubles.ids import SeededIdGenerator
from tests.golden.harness import golden_path

GOLDEN_IDS = (
    "018f0d4e-7b6a-7000-8000-000000000501",
    "018f0d4e-7b6a-7000-8000-000000000502",
    "018f0d4e-7b6a-7000-8000-000000000503",
)


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []

    async def publish(
        self, event: EventEnvelope, *, capture_id: str | None = None
    ) -> EventEnvelope:
        self.events.append(event)
        return event


def fixture_path() -> Path:
    return golden_path(Path("tests/golden"), "phase12-protocol.lpcap")


@pytest.mark.component
def test_golden_protocol_capture_fixture_is_integrity_valid(tmp_path: Path) -> None:
    unpacked = unpack_capture(fixture_path(), tmp_path / "capture")
    package = CapturePackage.open(unpacked)
    report = package.verify_or_raise()
    object_entry = package.manifest.objects[0]

    assert report.valid
    assert package.manifest.fidelity == "protocol"
    assert package.objects.read(object_entry.digest) == b"LUMORA-SYNTHETIC-DICOM-OBJECT-v1\n"


@pytest.mark.asyncio
async def test_golden_event_replay_is_byte_comparable() -> None:
    with zipfile.ZipFile(fixture_path()) as archive:
        source = tuple(
            EventEnvelope.model_validate(json.loads(line))
            for line in archive.read("events.jsonl").splitlines()
        )
        expected_findings = archive.read("findings.json")

    first_publisher = RecordingPublisher()
    second_publisher = RecordingPublisher()
    first = await EventReplayService(
        first_publisher,
        id_generator=SeededIdGenerator(GOLDEN_IDS),
    ).replay(source)
    second = await EventReplayService(
        second_publisher,
        id_generator=SeededIdGenerator(GOLDEN_IDS),
    ).replay(source)

    first_bytes = b"".join(event.to_json_bytes() + b"\n" for event in first.events)
    second_bytes = b"".join(event.to_json_bytes() + b"\n" for event in second.events)
    assert first_bytes == second_bytes
    assert json.loads(expected_findings) == []
    assert (
        expected_findings
        == json.dumps(json.loads(expected_findings), separators=(",", ":")).encode() + b"\n"
    )
