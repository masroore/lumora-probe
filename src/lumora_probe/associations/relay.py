"""Service-agnostic relay primitives and protocol trace records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .network import (
    DICOMListener,
    DICOMSCUClient,
    DICOMSCUConfig,
    DICOM_SUCCESS,
    _c_store_payload,
)


class RelayMode(StrEnum):
    """Explicit observation topologies supported by the relay."""

    PASS_THROUGH = "pass-through"
    PERMISSIVE_STANDALONE = "permissive-standalone"
    DESTINATION_AE_INTERCEPTION = "destination-ae-interception"


@dataclass(frozen=True, slots=True)
class RelayConfig:
    """Relay topology; permissive and destination interception are never implicit."""

    mode: RelayMode = RelayMode.PASS_THROUGH
    upstream: DICOMSCUConfig | None = None
    destination_ae: str | None = None

    def __post_init__(self) -> None:
        mode = RelayMode(self.mode)
        object.__setattr__(self, "mode", mode)
        if mode is RelayMode.DESTINATION_AE_INTERCEPTION and not self.destination_ae:
            raise ValueError("destination-ae-interception requires destination_ae")
        if self.destination_ae is not None and not self.destination_ae.strip():
            raise ValueError("destination_ae must not be blank")

    @property
    def negotiation_label(self) -> str:
        """Return the operator-visible label for the selected negotiation topology."""
        if self.mode is RelayMode.PASS_THROUGH and self.upstream is None:
            return "pass-through-upstream-unavailable"
        return self.mode.value

    def require_upstream(self) -> DICOMSCUConfig:
        if self.upstream is None:
            raise RuntimeError(
                "pass-through relay requires an upstream peer; choose permissive-standalone "
                "explicitly to capture without one"
            )
        return self.upstream


class DICOMRelay(DICOMListener):
    """Inline relay endpoint with explicit pass-through or standalone semantics."""

    def __init__(self, config: Any, relay_config: RelayConfig, **kwargs: Any) -> None:
        super().__init__(config, **kwargs)
        self.relay_config = relay_config

    def _on_c_store(self, event: Any) -> int:
        payload = _c_store_payload(event)
        upstream = self.relay_config.upstream
        if upstream is None:
            payload = {
                **payload,
                "relay_mode": self.relay_config.negotiation_label,
                "upstream_forwarded": False,
            }
            self._publish_dimse_event(event.assoc, "CStoreReceived", payload)
            self._publish_dimse_event(event.assoc, "DatasetParsed", payload)
            return (
                DICOM_SUCCESS
                if self.relay_config.mode is RelayMode.PERMISSIVE_STANDALONE
                else 0xA700
            )

        result = DICOMSCUClient(upstream, clock=self.clock).store_dataset(
            event.dataset,
            abstract_syntax=str(event.context.abstract_syntax),
            transfer_syntax=str(event.context.transfer_syntax),
            file_meta=getattr(event, "file_meta", None),
        )
        payload = {
            **payload,
            "relay_mode": self.relay_config.negotiation_label,
            "upstream_forwarded": True,
            "upstream_success": result.success,
            "upstream_status": result.status,
            "probe_hop_duration_ns": result.duration_ns,
        }
        self._publish_dimse_event(event.assoc, "CStoreReceived", payload)
        self._publish_dimse_event(event.assoc, "DatasetParsed", payload)
        if result.success:
            self._publish_dimse_event(
                event.assoc,
                "InstancePersisted",
                {**payload, "destination": "upstream"},
            )
        return DICOM_SUCCESS if result.success else 0xA700

    def _on_c_echo(self, event: Any) -> int:
        upstream = self.relay_config.upstream
        if self.relay_config.mode is RelayMode.PASS_THROUGH and upstream is None:
            self._publish_dimse_event(
                event.assoc,
                "CEchoReceived",
                {
                    "dimse": "C-ECHO",
                    "relay_mode": self.relay_config.negotiation_label,
                    "upstream_forwarded": False,
                    "error": "upstream unavailable",
                    "pdu_count": 0,
                    "bytes": 0,
                    "first_monotonic_ns": None,
                    "last_monotonic_ns": None,
                    "max_inter_pdu_gap_ns": 0,
                },
            )
            return 0xA700
        if upstream is None:
            self._publish_dimse_event(
                event.assoc,
                "CEchoReceived",
                {
                    "dimse": "C-ECHO",
                    "relay_mode": self.relay_config.negotiation_label,
                    "upstream_forwarded": False,
                    "pdu_count": 0,
                    "bytes": 0,
                    "first_monotonic_ns": None,
                    "last_monotonic_ns": None,
                    "max_inter_pdu_gap_ns": 0,
                },
            )
            return DICOM_SUCCESS
        result = DICOMSCUClient(upstream, clock=self.clock)._echo_sync()
        self._publish_dimse_event(
            event.assoc,
            "CEchoReceived",
            {
                "dimse": "C-ECHO",
                "relay_mode": self.relay_config.negotiation_label,
                "upstream_forwarded": True,
                "upstream_success": result.success,
                "upstream_status": result.status,
                "probe_hop_duration_ns": result.duration_ns,
                "pdu_count": 0,
                "bytes": 0,
                "first_monotonic_ns": None,
                "last_monotonic_ns": None,
                "max_inter_pdu_gap_ns": 0,
            },
        )
        return DICOM_SUCCESS if result.success else 0xA700


@dataclass(frozen=True, slots=True)
class PresentationContextPlan:
    """Accepted context mirrored from upstream to the downstream leg."""

    context_id: int
    abstract_syntax: str
    transfer_syntaxes: tuple[str, ...]


class PassThroughNegotiator:
    """Build a downstream context plan from upstream's accepted contexts."""

    def mirror(
        self,
        accepted_contexts: Iterable[Mapping[str, Any]],
        *,
        requested_abstract_syntaxes: Iterable[str] = (),
    ) -> tuple[PresentationContextPlan, ...]:
        requested = {str(value) for value in requested_abstract_syntaxes}
        plans: list[PresentationContextPlan] = []
        for context in accepted_contexts:
            abstract_syntax = str(context.get("abstract_syntax", ""))
            if requested and abstract_syntax not in requested:
                continue
            context_id = context.get("context_id")
            if type(context_id) is not int or context_id % 2 == 0:
                raise ValueError("presentation context IDs must be odd integers")
            transfer_syntaxes = context.get("transfer_syntaxes", ())
            if isinstance(transfer_syntaxes, (str, bytes)):
                transfer_syntaxes = (transfer_syntaxes,)
            plans.append(
                PresentationContextPlan(
                    context_id=context_id,
                    abstract_syntax=abstract_syntax,
                    transfer_syntaxes=tuple(str(value) for value in transfer_syntaxes),
                )
            )
        return tuple(plans)


@dataclass(frozen=True, slots=True)
class PDUTraceRecord:
    """Compact off-bus protocol trace row."""

    association_id: str
    direction: str
    pdu_type: str
    length: int
    declared_length: int | None
    presentation_context_ids: tuple[int, ...]
    pdv_boundaries: tuple[tuple[int, int], ...]
    monotonic_ns: int
    raw_sha256: str

    def as_dict(self) -> dict[str, object]:
        return {
            "association_id": self.association_id,
            "direction": self.direction,
            "pdu_type": self.pdu_type,
            "length": self.length,
            "declared_length": self.declared_length,
            "presentation_context_ids": self.presentation_context_ids,
            "pdv_boundaries": self.pdv_boundaries,
            "monotonic_ns": self.monotonic_ns,
            "raw_sha256": self.raw_sha256,
        }


class PDUTraceWriter:
    """Append compact JSON trace rows without passing them through the event bus."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("ab")

    def append(self, record: PDUTraceRecord) -> None:
        self._handle.write(json.dumps(record.as_dict(), separators=(",", ":")).encode("utf-8"))
        self._handle.write(b"\n")
        self._handle.flush()

    def flush(self) -> None:
        self._handle.flush()

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.flush()
            self._handle.close()

    def __enter__(self) -> PDUTraceWriter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class ByteFaithfulRelay:
    """Forward bytes unchanged and record only compact framing metadata."""

    def __init__(
        self,
        *,
        trace_writer: PDUTraceWriter | None = None,
        trace_clock: Callable[[], int] | None = None,
        diagnostic_sink: Callable[[str, Mapping[str, object]], None] | None = None,
    ) -> None:
        self.trace_writer = trace_writer
        self.trace_clock = trace_clock or (lambda: 0)
        self.diagnostic_sink = diagnostic_sink

    def forward(
        self,
        data: bytes,
        *,
        association_id: str,
        direction: str,
        send: Callable[[bytes], object] | None = None,
    ) -> bytes:
        """Return and optionally send exactly ``data``; never parse-and-re-encode it."""
        original = bytes(data)
        if send is not None:
            send(original)
        record, malformed = _trace_record(
            original,
            association_id=association_id,
            direction=direction,
            monotonic_ns=self.trace_clock(),
        )
        if self.trace_writer is not None:
            self.trace_writer.append(record)
        if malformed and self.diagnostic_sink is not None:
            self.diagnostic_sink(
                "malformed-pdu",
                {"association_id": association_id, "direction": direction, "length": len(original)},
            )
        return original


def _trace_record(
    data: bytes,
    *,
    association_id: str,
    direction: str,
    monotonic_ns: int,
) -> tuple[PDUTraceRecord, bool]:
    pdu_type = _PDU_TYPES.get(data[0], "Unknown") if data else "Empty"
    declared_length: int | None = None
    malformed = len(data) < 6
    if len(data) >= 6:
        declared_length = int.from_bytes(data[2:6], "big")
        malformed = declared_length != len(data) - 6
    return (
        PDUTraceRecord(
            association_id=association_id,
            direction=direction,
            pdu_type=pdu_type,
            length=len(data),
            declared_length=declared_length,
            presentation_context_ids=(),
            pdv_boundaries=(),
            monotonic_ns=monotonic_ns,
            raw_sha256=hashlib.sha256(data).hexdigest(),
        ),
        malformed,
    )


_PDU_TYPES = {
    0x01: "A-ASSOCIATE-RQ",
    0x02: "A-ASSOCIATE-AC",
    0x03: "A-ASSOCIATE-RJ",
    0x04: "P-DATA-TF",
    0x05: "A-RELEASE-RQ",
    0x06: "A-RELEASE-RP",
    0x07: "A-ABORT",
}


__all__ = [
    "ByteFaithfulRelay",
    "DICOMRelay",
    "PDUTraceRecord",
    "PDUTraceWriter",
    "PassThroughNegotiator",
    "PresentationContextPlan",
    "RelayConfig",
    "RelayMode",
]
