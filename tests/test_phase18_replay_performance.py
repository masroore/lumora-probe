# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Phase 18 replay orchestration performance evidence (injected sleeper)."""

from __future__ import annotations

import time

import pytest
from pydicom.uid import ExplicitVRLittleEndian

from lumora_probe.associations.contracts import DICOMStoreResult
from lumora_probe.replay.contracts import ProtocolReplayDataset, ProtocolReplayPolicy
from lumora_probe.replay.service import ProtocolReplayService
from lumora_probe.shared.value_objects import NetworkEndpoint


class CountingSender:
    def __init__(self) -> None:
        self.calls = 0

    async def send_dataset(self, data: bytes, *, transfer_syntax: str) -> DICOMStoreResult:
        self.calls += 1
        return DICOMStoreResult(success=True, status=0x0000, duration_ns=1)


@pytest.mark.component
@pytest.mark.asyncio
async def test_protocol_replay_orchestration_cost_for_five_hundred_records() -> None:
    sender = CountingSender()
    sleeps: list[float] = []

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    target = NetworkEndpoint("127.0.0.1", 11112)
    policy = ProtocolReplayPolicy(target=target, allowed_targets=frozenset({target}), dry_run=False)
    datasets = tuple(
        ProtocolReplayDataset(
            raw_bytes=f"dataset-{index}".encode(),
            transfer_syntax=ExplicitVRLittleEndian,
            monotonic_ns=index * 1_000_000,
        )
        for index in range(500)
    )
    started = time.monotonic()
    result = await ProtocolReplayService(sender, policy=policy, sleeper=sleeper).replay(
        datasets,
        capture_fidelity="protocol",
        speed=1.0,
    )
    elapsed = time.monotonic() - started

    assert result.count == 500
    assert result.success_count == 500
    assert sender.calls == 500
    assert len(sleeps) == 499
    assert all(delay == pytest.approx(0.001) for delay in sleeps[:5])
    print(
        {
            "dimension": "replay_orchestration",
            "records": 500,
            "elapsed_seconds": elapsed,
            "reconstructed_delay_count": len(sleeps),
        }
    )
