"""pynetdicom SCP setup and DIMSE event handlers."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumora_dicom_common.constants import DICOM_SUCCESS_STATUS

from .config import Config
from .log import ProbeLogger
from .storage import InvalidDatasetError, Storage, StorageError

SUCCESS = DICOM_SUCCESS_STATUS
OUT_OF_RESOURCES = 0xA700
DATASET_DOES_NOT_MATCH_SOP_CLASS = 0xA900
CANNOT_UNDERSTAND = 0xC000


@dataclass(slots=True)
class _AssociationState:
    started_at: float
    instances_received: int = 0


class ProbeReceiver:
    """A C-STORE/C-ECHO SCP backed by the local filesystem."""

    def __init__(
        self,
        config: Config,
        logger: ProbeLogger | None = None,
        storage: Storage | None = None,
    ) -> None:
        self.config = config
        self.logger = logger or ProbeLogger(config.log_format)
        self.storage = storage or Storage(config.output)
        self.ae: Any = None
        self.server: Any = None
        self.started_at: float | None = None
        self.total_instances = 0
        self.total_associations = 0
        self._states: dict[int, _AssociationState] = {}
        self._lock = threading.Lock()

    def _build_ae(self) -> Any:
        try:
            from pynetdicom import AE, AllStoragePresentationContexts, evt

            try:
                from pynetdicom import ALL_TRANSFER_SYNTAXES
            except ImportError:
                from pynetdicom._globals import ALL_TRANSFER_SYNTAXES
            try:
                from pynetdicom import _config
            except ImportError:
                import pynetdicom._config as _config  # noqa: PLR0402  -- fallback for older pynetdicom layout

            from pynetdicom.sop_class import Verification
        except ImportError as exc:
            raise RuntimeError(
                "pynetdicom and pydicom are required; install project dependencies first"
            ) from exc

        ae = AE(ae_title=self.config.ae_title)
        ae.maximum_pdu_size = self.config.max_pdu
        # Probe Lite is intentionally a generic receiver: private and unknown public
        # storage SOP Classes must be negotiated instead of being silently refused.
        _config.LOG_HANDLER_LEVEL = "none"
        _config.STORE_RECV_CHUNKED_DATASET = True
        _config.UNRESTRICTED_STORAGE_SERVICE = True
        ae.supported_contexts = []
        abstract_syntaxes = {
            str(context.abstract_syntax) for context in AllStoragePresentationContexts
        }
        for abstract_syntax in abstract_syntaxes:
            ae.add_supported_context(abstract_syntax, ALL_TRANSFER_SYNTAXES)
        ae.add_supported_context(Verification, ALL_TRANSFER_SYNTAXES)
        if self.config.accept_ae:
            ae.require_calling_aet = sorted(self.config.accept_ae)

        handlers = [
            (evt.EVT_REQUESTED, self._on_association_requested),
            (evt.EVT_ACCEPTED, self._on_association_accepted),
            (evt.EVT_REJECTED, self._on_association_rejected),
            (evt.EVT_RELEASED, self._on_association_released),
            (evt.EVT_ABORTED, self._on_association_aborted),
            (evt.EVT_C_ECHO, self._on_c_echo),
            (evt.EVT_C_STORE, self._on_c_store),
        ]
        if self.config.verbose:
            handlers.append((evt.EVT_ESTABLISHED, self._on_association_detail))
        ae._probe_lite_handlers = handlers
        return ae

    def start(self) -> None:
        """Bind the listen socket and return once the SCP is accepting connections."""
        if self.server is not None:
            raise RuntimeError("receiver is already running")
        self.ae = self._build_ae()
        try:
            self.server = self.ae.start_server(
                ("", self.config.port), block=False, evt_handlers=self.ae._probe_lite_handlers
            )
        except OSError:
            self.ae = None
            raise
        self.started_at = time.monotonic()
        self.logger.info(
            "startup",
            port=self.config.port,
            ae_title=self.config.ae_title,
            output_directory=str(Path(self.config.output)),
            accepted_aes=sorted(self.config.accept_ae) if self.config.accept_ae else "any",
        )

    def serve(self, stop_event: threading.Event) -> None:
        """Block until a caller signals shutdown."""
        self.start()
        stop_event.wait()
        self.stop()

    def stop(self, grace_period: float = 5.0) -> None:
        """Stop accepting work and allow active associations to finish."""
        if self.server is None:
            return
        server = self.server
        self.server = None
        server.shutdown()
        deadline = time.monotonic() + grace_period
        while self.ae is not None and self.ae.active_associations and time.monotonic() < deadline:
            time.sleep(0.05)
        if self.ae is not None:
            self.ae.shutdown()
        uptime = time.monotonic() - self.started_at if self.started_at else 0.0
        self.logger.info(
            "shutdown",
            total_instances=self.total_instances,
            total_associations=self.total_associations,
            uptime_seconds=round(uptime, 3),
        )

    def _on_association_requested(self, event: Any) -> None:
        assoc = event.assoc
        with self._lock:
            self._states[id(assoc)] = _AssociationState(time.monotonic())
        self.logger.info(
            "association_requested",
            calling_ae=_calling_ae(assoc),
            called_ae=_called_ae(assoc),
            peer=_peer(assoc),
        )
        if self.config.verbose:
            self._log_contexts(assoc, requested=True)

    def _on_association_accepted(self, event: Any) -> None:
        assoc = event.assoc
        with self._lock:
            self._states.setdefault(id(assoc), _AssociationState(time.monotonic()))
            self.total_associations += 1
        self.logger.info(
            "association_accepted",
            calling_ae=_calling_ae(assoc),
            peer=_peer(assoc),
            contexts=len(getattr(assoc, "accepted_contexts", [])),
        )
        if self.config.verbose:
            self._log_contexts(assoc)

    def _on_association_rejected(self, event: Any) -> None:
        assoc = event.assoc
        self.logger.warning(
            "association_rejected",
            calling_ae=_calling_ae(assoc),
            peer=_peer(assoc),
            reason="calling AE not allowed" if self.config.accept_ae else "rejected by peer",
        )

    def _on_association_released(self, event: Any) -> None:
        self._finish_association(event.assoc, "association_released")

    def _on_association_aborted(self, event: Any) -> None:
        assoc = event.assoc
        self._finish_association(
            assoc,
            "association_aborted",
            abort_source=getattr(getattr(assoc, "dul", None), "abort_source", "unknown"),
        )

    def _finish_association(self, assoc: Any, event_name: str, **fields: Any) -> None:
        with self._lock:
            state = self._states.pop(id(assoc), None)
        duration = time.monotonic() - state.started_at if state else 0.0
        self.logger.info(
            event_name,
            calling_ae=_calling_ae(assoc),
            peer=_peer(assoc),
            duration_seconds=round(duration, 3),
            instances_received=state.instances_received if state else 0,
            **fields,
        )

    def _on_c_echo(self, event: Any) -> int:
        self.logger.info(
            "c_echo_received", calling_ae=_calling_ae(event.assoc), peer=_peer(event.assoc)
        )
        return SUCCESS

    def _on_c_store(self, event: Any) -> int:
        request = event.request
        sop_instance_uid = _request_value(request, "AffectedSOPInstanceUID", "unknown")
        try:
            stored = self.storage.write_dataset(event.dataset, getattr(event, "file_meta", None))
        except InvalidDatasetError as exc:
            self.logger.error(
                "instance_store_failed",
                sop_instance_uid=sop_instance_uid,
                error=str(exc),
                status="0xA900",
            )
            return DATASET_DOES_NOT_MATCH_SOP_CLASS
        except StorageError as exc:
            self.logger.error(
                "instance_store_failed",
                sop_instance_uid=sop_instance_uid,
                error=str(exc),
                status="0xA700",
            )
            return OUT_OF_RESOURCES
        except Exception as exc:  # noqa: BLE001  -- store-handler error tolerance per plan §1.4/§10.7
            return self._fallback_raw(event, sop_instance_uid, exc)

        transfer_syntax = getattr(getattr(event, "context", None), "transfer_syntax", "unknown")
        dataset = event.dataset
        self._increment_instance(event.assoc)
        self.logger.info(
            "instance_received",
            sop_instance_uid=str(getattr(dataset, "SOPInstanceUID", sop_instance_uid)),
            sop_class_uid=str(
                getattr(
                    dataset,
                    "SOPClassUID",
                    _request_value(request, "AffectedSOPClassUID", "unknown"),
                )
            ),
            transfer_syntax=str(transfer_syntax),
            study_uid=str(getattr(dataset, "StudyInstanceUID", "unknown")),
            series_uid=str(getattr(dataset, "SeriesInstanceUID", "unknown")),
            file_path=str(stored.path),
            size_bytes=stored.size,
        )
        return SUCCESS

    def _fallback_raw(self, event: Any, sop_instance_uid: str, cause: Exception) -> int:
        try:
            try:
                raw_bytes = event.encoded_dataset()
            except Exception:  # noqa: BLE001  -- raw-dataset fallback across pynetdicom versions
                request = getattr(event, "request", None)
                raw_bytes = request.DataSet if request is not None else None
            if hasattr(raw_bytes, "getvalue"):
                raw_bytes = raw_bytes.getvalue()
            if not isinstance(raw_bytes, bytes):
                raw_bytes = bytes(raw_bytes)
        except Exception as raw_exc:  # noqa: BLE001  -- raw-dataset fallback tolerance
            self.logger.error(
                "instance_store_failed",
                sop_instance_uid=sop_instance_uid,
                error=f"{cause}; malformed request could not be decoded: {raw_exc}",
                status="0xC000",
            )
            return CANNOT_UNDERSTAND
        try:
            stored = self.storage.write_raw(sop_instance_uid, raw_bytes)
        except InvalidDatasetError as raw_exc:
            self.logger.error(
                "instance_store_failed",
                sop_instance_uid=sop_instance_uid,
                error=f"{cause}; malformed SOP Instance UID: {raw_exc}",
                status="0xC000",
            )
            return CANNOT_UNDERSTAND
        except StorageError as raw_exc:
            self.logger.error(
                "instance_store_failed",
                sop_instance_uid=sop_instance_uid,
                error=f"{cause}; raw fallback failed: {raw_exc}",
                status="0xA700",
            )
            return OUT_OF_RESOURCES
        self.logger.warning(
            "instance_store_failed",
            sop_instance_uid=sop_instance_uid,
            error=f"dataset parse/write failed; raw bytes preserved: {cause}",
            file_path=str(stored.path),
            size_bytes=stored.size,
            status="0xA900",
        )
        return DATASET_DOES_NOT_MATCH_SOP_CLASS

    def _increment_instance(self, assoc: Any) -> None:
        with self._lock:
            self.total_instances += 1
            state = self._states.get(id(assoc))
            if state:
                state.instances_received += 1

    def _on_association_detail(self, event: Any) -> None:
        if self.config.verbose:
            self._log_contexts(event.assoc)

    def _log_contexts(self, assoc: Any, requested: bool = False) -> None:
        service_user = getattr(assoc, "requestor", None)
        source = getattr(service_user, "requested_contexts", None) if requested else None
        source = source or getattr(assoc, "accepted_contexts", [])
        extended_negotiation = getattr(service_user, "extended_negotiation", [])
        contexts = []
        for context in source:
            transfer_syntax = getattr(context, "transfer_syntax", [])
            if isinstance(transfer_syntax, (str, bytes)):
                transfer_syntax = [transfer_syntax]
            contexts.append(
                {
                    "id": getattr(context, "context_id", "unknown"),
                    "abstract_syntax": str(getattr(context, "abstract_syntax", "unknown")),
                    "transfer_syntax": [str(item) for item in transfer_syntax],
                }
            )
        self.logger.info(
            "association_negotiation",
            calling_ae=_calling_ae(assoc),
            contexts=contexts,
            extended_negotiation=[str(item) for item in extended_negotiation],
        )


def _service_user(assoc: Any, name: str) -> Any:
    return getattr(assoc, name, None) or getattr(assoc, "requestor", None)


def _calling_ae(assoc: Any) -> str:
    requestor = _service_user(assoc, "requestor")
    title = getattr(requestor, "ae_title", "")
    if not title:
        title = getattr(getattr(requestor, "primitive", None), "calling_ae_title", "unknown")
    return _as_text(title)


def _called_ae(assoc: Any) -> str:
    return _as_text(getattr(_service_user(assoc, "acceptor"), "ae_title", "unknown"))


def _peer(assoc: Any) -> str:
    remote = getattr(assoc, "remote", None)
    if isinstance(remote, dict):
        address = remote.get("address")
        port = remote.get("port")
        if address is not None:
            return f"{address}:{port}" if port is not None else _as_text(address)
    requestor = getattr(assoc, "requestor", None)
    address = _as_text(getattr(requestor, "address", "unknown"))
    port = getattr(requestor, "port", None)
    return f"{address}:{port}" if port is not None else address


def _as_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("ascii", errors="replace").strip()
    return str(value)


def _request_value(request: Any, name: str, default: str) -> str:
    value = getattr(request, name, default)
    return _as_text(value) if value is not None else default
