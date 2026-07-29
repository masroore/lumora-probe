"""Phase 12 protocol replay acceptance tests."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from typing import Any

import pytest
from pydicom import dcmwrite
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian

from lumora_probe.associations.contracts import DICOMSCUConfig, DICOMStoreResult
from lumora_probe.associations.network import DICOMSCUClient
from lumora_probe.core.operations import CancellationToken
from lumora_probe.replay.contracts import ProtocolReplayDataset, ProtocolReplayPolicy
from lumora_probe.replay.service import InMemoryReplayExclusivity, ProtocolReplayService
from lumora_probe.shared.errors import ReplayDomainError
from lumora_probe.shared.value_objects import NetworkEndpoint
from tests.doubles.clock import ControllableClock


class FakeDatasetSender:
    def __init__(self, results: list[DICOMStoreResult]) -> None:
        self.results = iter(results)
        self.calls: list[tuple[bytes, str]] = []

    async def send_dataset(self, data: bytes, *, transfer_syntax: str) -> DICOMStoreResult:
        self.calls.append((data, transfer_syntax))
        return next(self.results)


def policy(*, dry_run: bool = False):
    target = NetworkEndpoint("127.0.0.1", 11112)
    return ProtocolReplayPolicy(target=target, allowed_targets=frozenset({target}), dry_run=dry_run)


def dataset(index: int, *, monotonic_ns: int) -> ProtocolReplayDataset:
    return ProtocolReplayDataset(
        raw_bytes=f"dataset-{index}".encode(),
        transfer_syntax=ExplicitVRLittleEndian,
        monotonic_ns=monotonic_ns,
    )


def clock() -> ControllableClock:
    return ControllableClock(datetime(2026, 7, 29, tzinfo=UTC))


@pytest.mark.asyncio
async def test_protocol_replay_sends_order_and_reconstructs_monotonic_timing() -> None:
    sender = FakeDatasetSender(
        [
            DICOMStoreResult(success=True, status=0x0000, duration_ns=1),
            DICOMStoreResult(success=True, status=0x0000, duration_ns=1),
            DICOMStoreResult(success=False, status=0xC000, duration_ns=1, error="rejected"),
        ]
    )
    sleeps: list[float] = []

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    result = await ProtocolReplayService(sender, policy=policy(), sleeper=sleeper).replay(
        [
            dataset(0, monotonic_ns=100),
            dataset(1, monotonic_ns=2_100),
            dataset(2, monotonic_ns=5_100),
        ],
        capture_fidelity="protocol",
        speed=2.0,
    )

    assert [data for data, _ in sender.calls] == [b"dataset-0", b"dataset-1", b"dataset-2"]
    assert sleeps == [1e-6, 1.5e-6]
    assert result.count == 3
    assert result.success_count == 2
    assert result.failure_count == 1
    assert result.planned == 3


@pytest.mark.asyncio
async def test_protocol_replay_rejects_non_monotonic_input_before_network_send() -> None:
    sender = FakeDatasetSender([])

    with pytest.raises(ReplayDomainError, match="not monotonic"):
        await ProtocolReplayService(sender, policy=policy()).replay(
            [dataset(0, monotonic_ns=2), dataset(1, monotonic_ns=1)],
            capture_fidelity="protocol",
        )

    assert sender.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("capture_fidelity", ["events", "objects"])
async def test_protocol_replay_refuses_capture_without_protocol_stream(
    capture_fidelity: str,
) -> None:
    sender = FakeDatasetSender([])

    with pytest.raises(ReplayDomainError, match="pdus.jsonl"):
        await ProtocolReplayService(sender, policy=policy()).replay(
            [dataset(0, monotonic_ns=1)],
            capture_fidelity=capture_fidelity,
        )

    assert sender.calls == []


@pytest.mark.asyncio
async def test_protocol_replay_refuses_partial_promoted_window_before_network_send() -> None:
    sender = FakeDatasetSender([])

    with pytest.raises(ReplayDomainError, match="partial capture"):
        await ProtocolReplayService(sender, policy=policy()).replay(
            [dataset(0, monotonic_ns=1)],
            capture_fidelity="protocol",
            partial=True,
            incomplete_aggregates=("association-1",),
        )

    assert sender.calls == []


@pytest.mark.asyncio
async def test_protocol_replay_dry_run_does_not_send_to_target() -> None:
    sender = FakeDatasetSender([])
    target = NetworkEndpoint("127.0.0.1", 11112)
    result = await ProtocolReplayService(
        sender,
        policy=ProtocolReplayPolicy(
            target=target, allowed_targets=frozenset({target}), dry_run=True
        ),
    ).replay([dataset(0, monotonic_ns=1)], capture_fidelity="protocol")

    assert result.dry_run
    assert result.planned == 1
    assert result.count == 0
    assert sender.calls == []


@pytest.mark.asyncio
async def test_protocol_replay_requires_explicit_allowlisted_target() -> None:
    sender = FakeDatasetSender([])
    target = NetworkEndpoint("127.0.0.1", 11112)

    with pytest.raises(ReplayDomainError, match="explicitly configured target"):
        await ProtocolReplayService(
            sender,
            policy=ProtocolReplayPolicy(allowed_targets=frozenset({target})),
        ).replay([dataset(0, monotonic_ns=1)], capture_fidelity="protocol")

    other = NetworkEndpoint("127.0.0.1", 11113)
    with pytest.raises(ReplayDomainError, match="not allowlisted"):
        await ProtocolReplayService(
            sender,
            policy=ProtocolReplayPolicy(
                target=other,
                allowed_targets=frozenset({target}),
                dry_run=False,
            ),
        ).replay([dataset(0, monotonic_ns=1)], capture_fidelity="protocol")

    assert sender.calls == []


@pytest.mark.asyncio
async def test_protocol_replay_audit_sink_records_completed_run() -> None:
    sender = FakeDatasetSender([DICOMStoreResult(success=True, status=0x0000, duration_ns=1)])
    records: list[Any] = []
    result = await ProtocolReplayService(
        sender,
        policy=policy(),
        audit_sink=records.append,
        clock=clock(),
    ).replay(
        [dataset(0, monotonic_ns=1)],
        capture_fidelity="protocol",
        replay_id="018f0d4e-7b6a-7000-8000-000000000201",
        capture_id="018f0d4e-7b6a-7000-8000-000000000202",
    )

    assert result.count == 1
    assert len(records) == 1
    assert records[0].outcome == "completed"
    assert records[0].replay_id == result.replay_id
    assert records[0].capture_id == result.capture_id
    assert records[0].confirmed_count == result.success_count


@pytest.mark.asyncio
async def test_protocol_replay_audit_sink_records_refusal() -> None:
    records: list[Any] = []
    target = NetworkEndpoint("127.0.0.1", 11112)

    with pytest.raises(ReplayDomainError):
        await ProtocolReplayService(
            FakeDatasetSender([]),
            policy=ProtocolReplayPolicy(allowed_targets=frozenset({target})),
            audit_sink=records.append,
            clock=clock(),
        ).replay(
            [dataset(0, monotonic_ns=1)],
            capture_fidelity="protocol",
            replay_id="018f0d4e-7b6a-7000-8000-000000000203",
        )

    assert len(records) == 1
    assert records[0].outcome == "refused"
    assert "target" in (records[0].error or "")


@pytest.mark.asyncio
async def test_protocol_replay_refuses_second_live_run_instead_of_queueing() -> None:
    target = NetworkEndpoint("127.0.0.1", 11112)
    exclusivity = InMemoryReplayExclusivity()
    exclusivity.acquire()

    try:
        with pytest.raises(ReplayDomainError, match="already running"):
            await ProtocolReplayService(
                FakeDatasetSender([]),
                policy=ProtocolReplayPolicy(
                    target=target,
                    allowed_targets=frozenset({target}),
                    dry_run=False,
                ),
                exclusivity=exclusivity,
            ).replay([dataset(0, monotonic_ns=1)], capture_fidelity="protocol")
    finally:
        exclusivity.release()


@pytest.mark.asyncio
async def test_protocol_replay_cancellation_reports_confirmed_count() -> None:
    cancellation = CancellationToken()

    class CancellingSender(FakeDatasetSender):
        async def send_dataset(self, data: bytes, *, transfer_syntax: str) -> DICOMStoreResult:
            result = await super().send_dataset(data, transfer_syntax=transfer_syntax)
            cancellation.cancel()
            return result

    sender = CancellingSender(
        [
            DICOMStoreResult(success=True, status=0x0000, duration_ns=1),
            DICOMStoreResult(success=True, status=0x0000, duration_ns=1),
        ]
    )
    result = await ProtocolReplayService(sender, policy=policy()).replay(
        [dataset(0, monotonic_ns=1), dataset(1, monotonic_ns=2)],
        capture_fidelity="protocol",
        cancellation=cancellation,
    )

    assert result.cancelled
    assert result.count == 1
    assert result.success_count == 1
    assert result.planned == 2


@pytest.mark.asyncio
async def test_protocol_replay_scu_parses_bytes_off_loop_and_derives_sop_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = Dataset()
    source.SOPClassUID = CTImageStorage
    source.SOPInstanceUID = "1.2.826.0.1.3680043.10.543.12"
    source.PatientName = "Synthetic^Replay"
    source.file_meta = FileMetaDataset()
    source.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    source.file_meta.MediaStorageSOPClassUID = CTImageStorage
    source.file_meta.MediaStorageSOPInstanceUID = source.SOPInstanceUID
    encoded = BytesIO()
    dcmwrite(encoded, source, write_like_original=False)

    client = DICOMSCUClient(DICOMSCUConfig(host="127.0.0.1", port=11112))
    captured: dict[str, Any] = {}

    def fake_store(
        parsed: Dataset,
        *,
        abstract_syntax: str,
        transfer_syntax: str,
        file_meta: FileMetaDataset | None,
    ) -> DICOMStoreResult:
        captured.update(
            parsed=parsed,
            abstract_syntax=abstract_syntax,
            transfer_syntax=transfer_syntax,
            file_meta=file_meta,
        )
        return DICOMStoreResult(success=True, status=0x0000, duration_ns=5)

    monkeypatch.setattr(client, "_store_sync", fake_store)
    result = await client.send_dataset(encoded.getvalue(), transfer_syntax=ExplicitVRLittleEndian)

    assert result.success
    assert captured["abstract_syntax"] == CTImageStorage
    assert captured["transfer_syntax"] == ExplicitVRLittleEndian
    assert captured["parsed"].SOPInstanceUID == source.SOPInstanceUID
