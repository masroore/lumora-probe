# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from lumora_probe.associations.domain import (
    Association,
    AssociationPair,
    AssociationPairState,
    AssociationState,
)
from lumora_probe.captures.domain import Capture, CaptureState
from lumora_probe.replay.domain import Replay, ReplayFidelity, ReplayMode, ReplayState
from lumora_probe.reports.domain import Report, ReportState
from lumora_probe.shared.errors import DomainInvariantError, InvalidStateTransitionError
from lumora_probe.shared.value_objects import (
    DICOMUID,
    AETitle,
    DICOMTag,
    Duration,
    FilePath,
    NetworkEndpoint,
    PixelDimensions,
    PresentationContext,
    Timestamp,
    TransferSyntax,
    WindowWidth,
)


def test_dicom_value_objects_are_frozen_and_validate_invariants() -> None:
    title = AETitle("LUMORA")
    assert str(title) == "LUMORA"
    with pytest.raises(DomainInvariantError):
        AETitle("é")
    with pytest.raises(DomainInvariantError):
        AETitle("A" * 17)

    uid = DICOMUID("1.2.840.10008.1.1")
    context = PresentationContext(1, uid, (TransferSyntax(uid),))
    assert context.id == 1
    assert context.transfer_syntaxes[0].value == uid.value
    with pytest.raises(DomainInvariantError):
        PresentationContext(2, uid, (uid,))
    with pytest.raises(DomainInvariantError):
        DICOMUID("not-a-uid")

    assert DICOMTag(0x0008, 0x0018).__str__() == "(0008,0018)"
    assert PixelDimensions(512, 512).rows == 512
    assert str(FilePath(Path("capture/events.jsonl"))) == "capture/events.jsonl"
    assert Duration(datetime.resolution).value == datetime.resolution
    assert Timestamp(datetime(2026, 7, 29, tzinfo=UTC)).value.tzinfo is UTC
    with pytest.raises(DomainInvariantError):
        WindowWidth(0)


def test_association_lifecycle_and_domain_errors() -> None:
    association = Association(
        "assoc-1",
        AETitle("CALLING"),
        AETitle("CALLED"),
        local_endpoint=NetworkEndpoint("127.0.0.1", 11112),
    )
    association.begin_negotiation()
    association.establish()
    association.release()
    association.archive()
    assert association.status is AssociationState.ARCHIVED
    with pytest.raises(InvalidStateTransitionError):
        association.release()


def test_association_pair_preserves_three_independent_legs() -> None:
    def make_leg(identifier: str) -> Association:
        return Association(identifier, "CALLING", "CALLED")

    pair = AssociationPair("pair-1", make_leg("down"), make_leg("hop"), make_leg("up"))
    pair.begin_negotiation()
    pair.establish()
    assert pair.status is AssociationPairState.ESTABLISHED
    assert [leg.status for leg in pair.legs] == [AssociationState.ESTABLISHED] * 3
    pair.release()
    assert [leg.status for leg in pair.legs] == [AssociationState.RELEASED] * 3


def test_capture_lifecycle_includes_interrupted_and_promotion_metadata() -> None:
    capture = Capture("capture-1", promoted_from_buffer=True, partial=True)
    capture.start()
    capture.add_association("assoc-1")
    capture.stop()
    capture.complete()
    capture.archive()
    assert capture.status is CaptureState.ARCHIVED
    assert capture.association_ids == ("assoc-1",)

    interrupted = Capture("capture-2")
    interrupted.start()
    interrupted.interrupt("shutdown deadline")
    assert interrupted.status is CaptureState.INTERRUPTED
    assert interrupted.interruption_reason == "shutdown deadline"


def test_replay_requires_explicit_target_for_protocol_mode() -> None:
    event_replay = Replay("replay-1", "capture-1")
    event_replay.start()
    event_replay.complete()
    assert event_replay.status is ReplayState.COMPLETED

    with pytest.raises(DomainInvariantError):
        Replay("replay-2", "capture-1", mode=ReplayMode.PROTOCOL)

    protocol_replay = Replay(
        "replay-3",
        "capture-1",
        mode=ReplayMode.PROTOCOL,
        fidelity=ReplayFidelity.PROTOCOL,
        target=NetworkEndpoint("pacs.example", 11112),
    )
    protocol_replay.start()
    protocol_replay.pause()
    protocol_replay.resume()
    protocol_replay.complete()
    assert protocol_replay.required_fidelity is ReplayFidelity.PROTOCOL


def test_report_records_rule_set_version() -> None:
    report = Report("report-1", "capture-1", "seed-2026-07")
    report.generate()
    report.export()
    report.archive()
    assert report.status is ReportState.ARCHIVED
    assert report.rule_set_version == "seed-2026-07"
