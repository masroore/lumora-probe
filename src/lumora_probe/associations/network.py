"""Pynetdicom endpoint foundation for the DICOM association plane."""

from __future__ import annotations

import asyncio
import concurrent.futures
import copy
import importlib
import threading
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, cast

from lumora_probe.core.lifecycle import ServiceHealth
from lumora_probe.shared.events import EventEnvelope, EventOrigin, EventSeverity
from lumora_probe.shared.value_objects import AETitle

DICOM_SUCCESS = 0x0000
DEFAULT_DICOM_PORT = 11112
DEFAULT_MAX_PDU = 16_382


class AssociationClock(Protocol):
    """Injected wall and monotonic time source for association observations."""

    def now(self) -> datetime: ...

    def monotonic_ns(self) -> int: ...


class AssociationIdGenerator(Protocol):
    """Injected UUIDv7 identity source for association observations."""

    def new_id(self) -> str: ...


class AssociationEventIngress(Protocol):
    """Minimal thread-safe event ingress required from the core bus."""

    def publish_from_thread(
        self, event: EventEnvelope, *, capture_id: str | None = None
    ) -> concurrent.futures.Future[EventEnvelope]: ...


class AssociationLogger(Protocol):
    """Minimal structured logger required by the audit adapter."""

    def info(self, event: str, **values: object) -> object: ...


class LoggingAssociationAuditSink:
    """Emit one structured audit record for every association lifecycle phase."""

    def __init__(self, logger: AssociationLogger) -> None:
        self.logger = logger

    def __call__(self, record: AssociationAuditRecord) -> None:
        self.logger.info(
            f"association_{record.phase}",
            association_id=record.association_id,
            calling_ae=record.calling_ae,
            called_ae=record.called_ae,
            source_ip=record.source_host,
            source_port=record.source_port,
            occurred_at=record.occurred_at.isoformat(),
            monotonic_ns=record.monotonic_ns,
            accepted_contexts=record.accepted_contexts,
            reason=record.reason,
        )


class AssociationAuditSink(Protocol):
    """Non-blocking callback for association lifecycle observations."""

    def __call__(self, record: AssociationAuditRecord) -> None: ...


class CStoreSink(Protocol):
    """Optional local persistence callback for a received C-STORE event."""

    def __call__(self, event: Any) -> int: ...


class PDUTraceSink(Protocol):
    """Off-bus sink for compact protocol trace rows."""

    def __call__(self, record: Mapping[str, object]) -> None: ...


@dataclass(frozen=True, slots=True)
class DICOMListenerConfig:
    """Configuration for one non-privileged DICOM SCP listener."""

    bind_host: str = "127.0.0.1"
    port: int = DEFAULT_DICOM_PORT
    ae_title: AETitle | str = "LUMORA"
    max_pdu: int = DEFAULT_MAX_PDU
    allowed_calling_aets: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.bind_host.strip() or any(character.isspace() for character in self.bind_host):
            raise ValueError("bind_host must be a non-empty host without whitespace")
        if (
            type(self.port) is not int
            or isinstance(self.port, bool)
            or not 1024 <= self.port <= 65535
        ):
            raise ValueError("port must be a non-privileged TCP port between 1024 and 65535")
        if type(self.max_pdu) is not int or not 4_096 <= self.max_pdu <= 131_072:
            raise ValueError("max_pdu must be between 4096 and 131072")
        title = self.ae_title if isinstance(self.ae_title, AETitle) else AETitle(self.ae_title)
        object.__setattr__(self, "ae_title", title)
        normalized = frozenset(_normalize_ae_title(value) for value in self.allowed_calling_aets)
        object.__setattr__(self, "allowed_calling_aets", normalized)


@dataclass(frozen=True, slots=True)
class DICOMSCUConfig:
    """Peer and calling identity configuration for the DICOM SCU."""

    host: str
    port: int
    calling_ae: AETitle | str = "LUMORA-SCU"
    called_ae: AETitle | str = "ANY-SCP"
    max_pdu: int = DEFAULT_MAX_PDU
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if not self.host.strip() or any(character.isspace() for character in self.host):
            raise ValueError("host must be a non-empty host without whitespace")
        if type(self.port) is not int or isinstance(self.port, bool) or not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if type(self.max_pdu) is not int or not 4_096 <= self.max_pdu <= 131_072:
            raise ValueError("max_pdu must be between 4096 and 131072")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        object.__setattr__(
            self,
            "calling_ae",
            self.calling_ae if isinstance(self.calling_ae, AETitle) else AETitle(self.calling_ae),
        )
        object.__setattr__(
            self,
            "called_ae",
            self.called_ae if isinstance(self.called_ae, AETitle) else AETitle(self.called_ae),
        )


@dataclass(frozen=True, slots=True)
class DICOMStoreResult:
    """Result of forwarding one C-STORE dataset."""

    success: bool
    status: int | None
    duration_ns: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class DICOMEchoResult:
    """Result of one C-ECHO verification attempt."""

    success: bool
    status: int | None
    duration_ns: int
    error: str | None = None


class DICOMSCUClient:
    """Async facade over a pynetdicom SCU verification association."""

    def __init__(self, config: DICOMSCUConfig, *, clock: AssociationClock | None = None) -> None:
        self.config = config
        self.clock = clock

    async def echo(self) -> DICOMEchoResult:
        """Establish, negotiate, verify, and release one association off the event loop."""
        return await asyncio.to_thread(self.echo_sync)

    def echo_sync(self) -> DICOMEchoResult:
        started = self._monotonic_ns()
        association: Any = None
        try:
            from pynetdicom import AE

            Verification: Any = importlib.import_module("pynetdicom.sop_class").Verification
        except ImportError as exc:
            raise RuntimeError("pynetdicom and pydicom are required for the DICOM SCU") from exc

        ae: Any = AE(ae_title=str(self.config.calling_ae))
        ae.maximum_pdu_size = self.config.max_pdu
        ae.acse_timeout = self.config.timeout_seconds
        ae.dimse_timeout = self.config.timeout_seconds
        ae.network_timeout = self.config.timeout_seconds
        ae.add_requested_context(Verification)
        try:
            association = ae.associate(
                self.config.host,
                self.config.port,
                ae_title=str(self.config.called_ae),
                max_pdu=self.config.max_pdu,
            )
            if not association.is_established:
                return DICOMEchoResult(
                    success=False,
                    status=None,
                    duration_ns=self._monotonic_ns() - started,
                    error="association was not established",
                )
            response = association.send_c_echo()
            status = _status_code(response)
            return DICOMEchoResult(
                success=status == DICOM_SUCCESS,
                status=status,
                duration_ns=self._monotonic_ns() - started,
                error=None if status == DICOM_SUCCESS else f"C-ECHO status 0x{status:04X}",
            )
        except Exception as exc:  # noqa: BLE001 - network boundary returns an explicit result
            return DICOMEchoResult(
                success=False,
                status=None,
                duration_ns=self._monotonic_ns() - started,
                error=str(exc),
            )
        finally:
            if association is not None and association.is_established:
                association.release()

    def iter_find(self, identifier: Any, *, query_model: str) -> Iterator[tuple[Any, Any | None]]:
        """Yield C-FIND responses from the configured peer."""
        yield from self._iter_query("find", identifier, query_model=query_model)

    def iter_get(self, identifier: Any, *, query_model: str) -> Iterator[tuple[Any, Any | None]]:
        """Yield C-GET responses from the configured peer."""
        yield from self._iter_query("get", identifier, query_model=query_model)

    def iter_move(
        self, identifier: Any, *, move_aet: str, query_model: str
    ) -> Iterator[tuple[Any, Any | None]]:
        """Yield C-MOVE progress responses from the configured peer."""
        yield from self._iter_query("move", identifier, query_model=query_model, move_aet=move_aet)

    def _iter_query(
        self,
        operation: str,
        identifier: Any,
        *,
        query_model: str,
        move_aet: str | None = None,
    ) -> Iterator[tuple[Any, Any | None]]:
        association: Any = None
        try:
            from pynetdicom import AE
        except ImportError as exc:
            raise RuntimeError("pynetdicom and pydicom are required for the DICOM SCU") from exc

        ae: Any = AE(ae_title=str(self.config.calling_ae))
        ae.maximum_pdu_size = self.config.max_pdu
        ae.acse_timeout = self.config.timeout_seconds
        ae.dimse_timeout = self.config.timeout_seconds
        ae.network_timeout = self.config.timeout_seconds
        ae.add_requested_context(query_model)
        try:
            association = ae.associate(
                self.config.host,
                self.config.port,
                ae_title=str(self.config.called_ae),
                max_pdu=self.config.max_pdu,
            )
            if not association.is_established:
                yield 0xA700, None
                return
            if operation == "find":
                responses = association.send_c_find(identifier, query_model)
            elif operation == "get":
                responses = association.send_c_get(identifier, query_model)
            elif operation == "move":
                assert move_aet is not None
                responses = association.send_c_move(identifier, move_aet, query_model)
            else:
                raise ValueError(f"unsupported query operation: {operation}")
            yield from responses
        finally:
            if association is not None and association.is_established:
                association.release()

    def store_dataset(
        self,
        dataset: Any,
        *,
        abstract_syntax: str,
        transfer_syntax: str,
        file_meta: Any | None = None,
    ) -> DICOMStoreResult:
        """Forward a parsed C-STORE dataset synchronously from a pynetdicom thread."""
        return self._store_sync(
            dataset,
            abstract_syntax=abstract_syntax,
            transfer_syntax=transfer_syntax,
            file_meta=file_meta,
        )

    def _store_sync(
        self,
        dataset: Any,
        *,
        abstract_syntax: str,
        transfer_syntax: str,
        file_meta: Any | None,
    ) -> DICOMStoreResult:
        started = self._monotonic_ns()
        association: Any = None
        try:
            from pynetdicom import AE
        except ImportError as exc:
            raise RuntimeError("pynetdicom and pydicom are required for the DICOM SCU") from exc

        outbound = copy.deepcopy(dataset)
        if file_meta is not None:
            outbound.file_meta = copy.deepcopy(file_meta)
        if not hasattr(outbound, "file_meta"):
            raise ValueError("C-STORE forwarding requires file metadata")
        outbound.file_meta.TransferSyntaxUID = transfer_syntax
        outbound.file_meta.MediaStorageSOPClassUID = str(outbound.SOPClassUID)
        outbound.file_meta.MediaStorageSOPInstanceUID = str(outbound.SOPInstanceUID)

        ae: Any = AE(ae_title=str(self.config.calling_ae))
        ae.maximum_pdu_size = self.config.max_pdu
        ae.acse_timeout = self.config.timeout_seconds
        ae.dimse_timeout = self.config.timeout_seconds
        ae.network_timeout = self.config.timeout_seconds
        ae.add_requested_context(abstract_syntax, transfer_syntax)
        try:
            association = ae.associate(
                self.config.host,
                self.config.port,
                ae_title=str(self.config.called_ae),
                max_pdu=self.config.max_pdu,
            )
            if not association.is_established:
                return DICOMStoreResult(
                    success=False,
                    status=None,
                    duration_ns=self._monotonic_ns() - started,
                    error="association was not established",
                )
            response = association.send_c_store(outbound)
            status = _status_code(response)
            return DICOMStoreResult(
                success=status == DICOM_SUCCESS,
                status=status,
                duration_ns=self._monotonic_ns() - started,
                error=None if status == DICOM_SUCCESS else f"C-STORE status 0x{status:04X}",
            )
        except Exception as exc:  # noqa: BLE001 - network boundary returns an explicit result
            return DICOMStoreResult(
                success=False,
                status=None,
                duration_ns=self._monotonic_ns() - started,
                error=str(exc),
            )
        finally:
            if association is not None and association.is_established:
                association.release()

    def _monotonic_ns(self) -> int:
        return self.clock.monotonic_ns() if self.clock is not None else 0


@dataclass(frozen=True, slots=True)
class AssociationAuditRecord:
    """Compact lifecycle observation emitted for every accepted association attempt."""

    association_id: str
    phase: str
    calling_ae: str
    called_ae: str
    source_host: str
    source_port: int | None
    occurred_at: datetime
    monotonic_ns: int
    accepted_contexts: tuple[dict[str, object], ...] = ()
    reason: str | None = None


@dataclass(slots=True)
class _PDUStats:
    count: int = 0
    bytes: int = 0
    first_ns: int | None = None
    last_ns: int | None = None
    max_gap_ns: int = 0

    def add(self, size: int, timestamp_ns: int) -> None:
        if self.first_ns is None:
            self.first_ns = timestamp_ns
        if self.last_ns is not None:
            self.max_gap_ns = max(self.max_gap_ns, timestamp_ns - self.last_ns)
        self.last_ns = timestamp_ns
        self.count += 1
        self.bytes += size


@dataclass(slots=True)
class _AssociationState:
    association_id: str
    calling_ae: str
    called_ae: str
    source_host: str
    source_port: int | None


class DICOMListener:
    """Threaded pynetdicom SCP with an injected, transport-neutral audit sink.

    The listener owns no asyncio loop and never publishes directly to the event bus. The
    sink is deliberately synchronous and must only enqueue work or hand it to the bus's
    thread-safe ingress.
    """

    name = "dicom-listener"

    def __init__(
        self,
        config: DICOMListenerConfig | None = None,
        *,
        audit_sink: AssociationAuditSink | None = None,
        event_ingress: AssociationEventIngress | None = None,
        c_store_sink: CStoreSink | None = None,
        pdu_trace_sink: PDUTraceSink | None = None,
        clock: AssociationClock | None = None,
        id_generator: AssociationIdGenerator | None = None,
    ) -> None:
        self.config = config or DICOMListenerConfig()
        self.audit_sink = audit_sink
        self.event_ingress = event_ingress
        self.c_store_sink = c_store_sink
        self.pdu_trace_sink = pdu_trace_sink
        self.clock = clock
        self.id_generator = id_generator
        self.ae: Any | None = None
        self.server: Any | None = None
        self._states: dict[int, _AssociationState] = {}
        self._pdu_stats: dict[str, _PDUStats] = {}
        self._lock = threading.Lock()
        self._started = False
        self._accepted_associations = 0

    @property
    def started(self) -> bool:
        return self._started

    @property
    def accepted_associations(self) -> int:
        return self._accepted_associations

    async def start(self) -> None:
        """Start the SCP without blocking the owning asyncio loop."""
        if self._started:
            return
        ae: Any = self._build_ae()
        self.ae = ae
        try:
            self.server = ae.start_server(
                (self.config.bind_host, self.config.port),
                block=False,
                evt_handlers=self._handlers(),
            )
        except Exception:
            self.ae = None
            self.server = None
            raise
        self._started = True

    async def stop(self) -> None:
        """Stop accepting associations and close the pynetdicom server."""
        server = self.server
        self.server = None
        if server is not None:
            server.shutdown()
        if self.ae is not None:
            self.ae.shutdown()
        self.ae = None
        with self._lock:
            self._states.clear()
        self._started = False

    async def stop_accepting(self) -> None:
        """Stop new associations before lifecycle drain begins."""
        server = self.server
        self.server = None
        if server is not None:
            server.shutdown()

    async def drain(self) -> None:
        """Allow pynetdicom association threads to complete their current work."""
        if self.ae is None:
            return
        for association in tuple(self.ae.active_associations):
            association.join(timeout=0.1)

    async def flush(self) -> None:
        """Listener has no durable buffers; capture services provide flushing."""

    async def health(self) -> ServiceHealth:
        alive = self._started and self.ae is not None and self.server is not None
        return ServiceHealth(
            name=self.name,
            ready=alive,
            alive=alive,
            detail=f"{self.config.bind_host}:{self.config.port}" if alive else "listener stopped",
        )

    def _build_ae(self) -> Any:
        try:
            from pynetdicom import (
                AE,
                ALL_TRANSFER_SYNTAXES,
                AllStoragePresentationContexts,
                QueryRetrievePresentationContexts,
                VerificationPresentationContexts,
                _config,
            )
        except ImportError as exc:
            raise RuntimeError(
                "pynetdicom and pydicom are required for the DICOM listener"
            ) from exc

        _config.LOG_HANDLER_LEVEL = "none"
        _config.UNRESTRICTED_STORAGE_SERVICE = True
        _config.STORE_RECV_CHUNKED_DATASET = True

        ae: Any = AE(ae_title=str(self.config.ae_title))
        ae.maximum_pdu_size = self.config.max_pdu
        ae.supported_contexts = []
        for context in (
            *AllStoragePresentationContexts,
            *QueryRetrievePresentationContexts,
            *VerificationPresentationContexts,
        ):
            ae.add_supported_context(str(context.abstract_syntax), ALL_TRANSFER_SYNTAXES)
        if self.config.allowed_calling_aets:
            ae.require_calling_aet = sorted(self.config.allowed_calling_aets)
        return ae

    def _handlers(self) -> list[tuple[Any, Callable[..., Any]]]:
        from pynetdicom import evt

        handlers: list[tuple[Any, Callable[..., Any]]] = [
            (evt.EVT_REQUESTED, self._on_requested),
            (evt.EVT_ACCEPTED, self._on_accepted),
            (evt.EVT_REJECTED, self._on_rejected),
            (evt.EVT_RELEASED, self._on_released),
            (evt.EVT_ABORTED, self._on_aborted),
            (evt.EVT_C_ECHO, self._on_c_echo),
            (evt.EVT_C_STORE, self._on_c_store),
        ]
        handlers.extend(
            [
                (evt.EVT_PDU_RECV, self._on_pdu_received),
                (evt.EVT_PDU_SENT, self._on_pdu_sent),
            ]
        )
        return handlers

    def _on_requested(self, event: Any) -> None:
        association = event.assoc
        calling_ae = _calling_ae(association)
        called_ae = _called_ae(association)
        source_host, source_port = _source_endpoint(association)
        state = _AssociationState(
            association_id=self._new_association_id(),
            calling_ae=calling_ae,
            called_ae=called_ae,
            source_host=source_host,
            source_port=source_port,
        )
        with self._lock:
            self._states[id(association)] = state
        self._emit(state, "requested")

    def _on_accepted(self, event: Any) -> None:
        association = event.assoc
        state = self._state_for(association)
        with self._lock:
            self._accepted_associations += 1
        self._emit(state, "accepted", accepted_contexts=_contexts(association))

    def _on_rejected(self, event: Any) -> None:
        association = event.assoc
        state = self._state_for(association)
        self._emit(state, "rejected", reason="association rejected")
        self._forget(association)

    def _on_released(self, event: Any) -> None:
        association = event.assoc
        state = self._state_for(association)
        self._emit(state, "released")
        self._forget(association)

    def _on_aborted(self, event: Any) -> None:
        association = event.assoc
        state = self._state_for(association)
        reason = str(getattr(getattr(association, "dul", None), "abort_source", "unknown"))
        self._emit(state, "aborted", reason=reason)
        self._forget(association)

    def _on_pdu_received(self, event: Any) -> None:
        self._trace_pdu(event, "received")

    def _on_pdu_sent(self, event: Any) -> None:
        self._trace_pdu(event, "sent")

    def _trace_pdu(self, event: Any, direction: str) -> None:
        state = self._state_for(event.assoc)
        pdu = getattr(event, "pdu", None)
        raw = b""
        try:
            encoded = pdu.encode() if pdu is not None else b""
            raw = encoded if isinstance(encoded, bytes) else bytes(encoded)
        except Exception:  # noqa: BLE001 - malformed PDU still receives a trace row
            raw = b""
        timestamp_ns = self.clock.monotonic_ns() if self.clock else 0
        pdu_type = type(pdu).__name__ if pdu is not None else "Unknown"
        if direction == "received" and (raw[:1] == b"\x04" or "P_DATA" in pdu_type.upper()):
            with self._lock:
                self._pdu_stats.setdefault(state.association_id, _PDUStats()).add(
                    len(raw), timestamp_ns
                )
        if self.pdu_trace_sink is None:
            return
        declared_length = int.from_bytes(raw[2:6], "big") if len(raw) >= 6 else None
        self.pdu_trace_sink(
            {
                "association_id": state.association_id,
                "direction": direction,
                "pdu_type": pdu_type,
                "length": len(raw),
                "declared_length": declared_length,
                "presentation_context_ids": _pdu_context_ids(pdu),
                "pdv_boundaries": _pdu_boundaries(pdu),
                "monotonic_ns": timestamp_ns,
            }
        )

    def _on_c_echo(self, event: Any) -> int:
        self._publish_dimse_event(
            event.assoc,
            "CEchoReceived",
            {
                "dimse": "C-ECHO",
                "pdu_count": 0,
                "bytes": 0,
                "first_monotonic_ns": None,
                "last_monotonic_ns": None,
                "max_inter_pdu_gap_ns": 0,
            },
        )
        return DICOM_SUCCESS

    def _on_c_store(self, event: Any) -> int:
        payload = c_store_payload(event)
        self._publish_dimse_event(event.assoc, "CStoreReceived", payload)
        self._publish_dimse_event(event.assoc, "DatasetParsed", payload)
        if self.c_store_sink is not None:
            return self.c_store_sink(event)
        return 0xA700

    def _state_for(self, association: Any) -> _AssociationState:
        with self._lock:
            state = self._states.get(id(association))
        if state is not None:
            return state
        source_host, source_port = _source_endpoint(association)
        return _AssociationState(
            association_id=self._new_association_id(),
            calling_ae=_calling_ae(association),
            called_ae=_called_ae(association),
            source_host=source_host,
            source_port=source_port,
        )

    def _forget(self, association: Any) -> None:
        with self._lock:
            self._states.pop(id(association), None)

    def _publish_dimse_event(
        self, association: Any, event_name: str, payload: dict[str, object]
    ) -> None:
        if self.event_ingress is None:
            return
        state = self._state_for(association)
        payload = {**payload, **self._summary_for(state.association_id)}
        event = EventEnvelope.create(
            event_name=event_name,
            event_version=1,
            correlation_id=state.association_id,
            aggregate_type="Association",
            aggregate_id=state.association_id,
            producer="association-manager",
            payload=payload,
            origin=EventOrigin.OBSERVED,
            clock=self._clock(),
            id_generator=self._id_generator(),
        )
        self.event_ingress.publish_from_thread(event)

    def _summary_for(self, association_id: str) -> dict[str, object]:
        stats = self._pdu_stats.get(association_id)
        if stats is None:
            return {
                "pdu_count": 0,
                "bytes": 0,
                "first_monotonic_ns": None,
                "last_monotonic_ns": None,
                "max_inter_pdu_gap_ns": 0,
            }
        return {
            "pdu_count": stats.count,
            "bytes": stats.bytes,
            "first_monotonic_ns": stats.first_ns,
            "last_monotonic_ns": stats.last_ns,
            "max_inter_pdu_gap_ns": stats.max_gap_ns,
        }

    def _id_generator(self) -> AssociationIdGenerator:
        if self.id_generator is None:
            raise RuntimeError("event ingress requires an injected association ID generator")
        return self.id_generator

    def _clock(self) -> AssociationClock:
        if self.clock is None:
            raise RuntimeError("audit sink requires an injected association clock")
        return self.clock

    def _new_association_id(self) -> str:
        if self.id_generator is None:
            if self.audit_sink is not None:
                raise RuntimeError("audit sink requires an injected association ID generator")
            return "association-" + str(id(self))
        return self.id_generator.new_id()

    def _emit(
        self,
        state: _AssociationState,
        phase: str,
        *,
        accepted_contexts: tuple[dict[str, object], ...] = (),
        reason: str | None = None,
    ) -> None:
        if self.audit_sink is None and self.event_ingress is None:
            return
        record = AssociationAuditRecord(
            association_id=state.association_id,
            phase=phase,
            calling_ae=state.calling_ae,
            called_ae=state.called_ae,
            source_host=state.source_host,
            source_port=state.source_port,
            occurred_at=self._clock().now(),
            monotonic_ns=self._clock().monotonic_ns(),
            accepted_contexts=accepted_contexts,
            reason=reason,
        )
        if self.audit_sink is not None:
            self.audit_sink(record)
        if self.event_ingress is not None:
            event = EventEnvelope.create(
                event_name=_event_name_for_phase(phase),
                event_version=1,
                correlation_id=state.association_id,
                aggregate_type="Association",
                aggregate_id=state.association_id,
                producer="association-manager",
                payload={
                    "calling_ae": record.calling_ae,
                    "called_ae": record.called_ae,
                    "source_host": record.source_host,
                    "source_port": record.source_port,
                    "accepted_contexts": record.accepted_contexts,
                    "reason": record.reason,
                },
                origin=EventOrigin.OBSERVED,
                clock=self._clock(),
                id_generator=self._id_generator(),
                severity=EventSeverity.WARNING
                if phase in {"rejected", "aborted"}
                else EventSeverity.INFO,
            )
            self.event_ingress.publish_from_thread(event)


def _service_user(association: Any, name: str) -> Any:
    return getattr(association, name, None) or getattr(association, "requestor", None)


def _calling_ae(association: Any) -> str:
    requestor = _service_user(association, "requestor")
    value = getattr(requestor, "ae_title", None)
    if not value:
        value = getattr(getattr(requestor, "primitive", None), "calling_ae_title", "unknown")
    return _text(value)


def _called_ae(association: Any) -> str:
    acceptor = _service_user(association, "acceptor")
    return _text(getattr(acceptor, "ae_title", "unknown"))


def _source_endpoint(association: Any) -> tuple[str, int | None]:
    remote = getattr(association, "remote", None)
    if isinstance(remote, dict):
        remote_value = cast(dict[str, Any], remote)
        return _text(remote_value.get("address", "unknown")), _port(remote_value.get("port"))
    requestor = getattr(association, "requestor", None)
    return _text(getattr(requestor, "address", "unknown")), _port(getattr(requestor, "port", None))


def _contexts(association: Any) -> tuple[dict[str, object], ...]:
    values: list[dict[str, object]] = []
    for context in getattr(association, "accepted_contexts", ()):
        syntaxes = getattr(context, "transfer_syntax", ())
        if isinstance(syntaxes, (str, bytes)):
            syntaxes = (syntaxes,)
        values.append(
            {
                "context_id": getattr(context, "context_id", None),
                "abstract_syntax": _text(getattr(context, "abstract_syntax", "unknown")),
                "transfer_syntaxes": tuple(_text(value) for value in syntaxes),
            }
        )
    return tuple(values)


def _event_name_for_phase(phase: str) -> str:
    names = {
        "requested": "AssociationStarted",
        "accepted": "AssociationAccepted",
        "rejected": "AssociationRejected",
        "released": "AssociationReleased",
        "aborted": "AssociationAborted",
    }
    try:
        return names[phase]
    except KeyError as exc:
        raise ValueError(f"unsupported association phase: {phase}") from exc


def _pdu_context_ids(pdu: Any) -> tuple[int, ...]:
    values: list[int] = []
    for item in getattr(pdu, "presentation_data_values", ()) or ():
        value = getattr(item, "presentation_context_id", None)
        if type(value) is int:
            values.append(value)
    return tuple(values)


def _pdu_boundaries(pdu: Any) -> tuple[tuple[int, int], ...]:
    values: list[tuple[int, int]] = []
    offset = 0
    for item in getattr(pdu, "presentation_data_values", ()) or ():
        value = getattr(item, "presentation_data_value", b"")
        raw = value if isinstance(value, bytes) else bytes(value)
        values.append((offset, len(raw)))
        offset += len(raw)
    return tuple(values)


def c_store_payload(event: Any) -> dict[str, object]:
    request = getattr(event, "request", None)
    dataset = getattr(event, "dataset", None)
    context = getattr(event, "context", None)
    encoded_size = 0
    try:
        raw = event.encoded_dataset()
        encoded_size = len(raw.getvalue() if hasattr(raw, "getvalue") else raw)
    except Exception:  # noqa: BLE001 - malformed traffic is observed, not repaired
        encoded_size = 0
    return {
        "dimse": "C-STORE",
        "sop_class_uid": _text(
            getattr(dataset, "SOPClassUID", getattr(request, "AffectedSOPClassUID", "unknown"))
        ),
        "sop_instance_uid": _text(
            getattr(
                dataset, "SOPInstanceUID", getattr(request, "AffectedSOPInstanceUID", "unknown")
            )
        ),
        "study_uid": _text(getattr(dataset, "StudyInstanceUID", "unknown")),
        "series_uid": _text(getattr(dataset, "SeriesInstanceUID", "unknown")),
        "transfer_syntax": _text(getattr(context, "transfer_syntax", "unknown")),
        "dataset_bytes": encoded_size,
        "bytes": 0,
        "pdu_count": 0,
        "first_monotonic_ns": None,
        "last_monotonic_ns": None,
        "max_inter_pdu_gap_ns": 0,
    }


def _status_code(response: Any) -> int:
    value = getattr(response, "Status", response)
    return int(value)


def _normalize_ae_title(value: str) -> str:
    return str(AETitle(value))


def _port(value: Any) -> int | None:
    return value if type(value) is int and not isinstance(value, bool) else None


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("ascii", errors="replace").strip()
    return str(value)


__all__ = [
    "DEFAULT_DICOM_PORT",
    "DEFAULT_MAX_PDU",
    "DICOM_SUCCESS",
    "AssociationAuditRecord",
    "AssociationAuditSink",
    "AssociationClock",
    "AssociationEventIngress",
    "AssociationIdGenerator",
    "AssociationLogger",
    "CStoreSink",
    "DICOMEchoResult",
    "DICOMListener",
    "DICOMListenerConfig",
    "DICOMSCUClient",
    "DICOMSCUConfig",
    "DICOMStoreResult",
    "LoggingAssociationAuditSink",
    "PDUTraceSink",
]
