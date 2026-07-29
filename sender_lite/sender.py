"""DICOM transport for Sender Lite: C-ECHO and C-STORE."""

from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydicom import dcmread

from .catalog import CatalogInstance, StudyBatch
from .config import Config
from .log import SenderLogger

try:
    import pynetdicom
    from pynetdicom.sop_class import Verification
except ImportError:
    pynetdicom = None  # type: ignore
    Verification = None  # type: ignore


# ---------------------------------------------------------------------------
# Result records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EchoResult:
    """Outcome of a C-ECHO run."""

    success: bool
    status: int | None
    duration: float
    error: str | None


@dataclass(frozen=True, slots=True)
class InstanceResult:
    """Outcome of a single C-STORE attempt."""

    sop_instance_uid: str
    sop_class_uid: str
    transfer_syntax_uid: str
    path: Path
    size_bytes: int
    status: str  # "success" | "warning" | "failure" | "cancelled"
    status_code: int | None
    reason: str | None
    duration: float


@dataclass(frozen=True, slots=True)
class StudyResult:
    """Aggregate outcome for a Study Batch."""

    study_uid: str
    attempted: int
    succeeded: int
    warned: int
    failed: int
    cancelled: int
    duration: float
    instances: tuple[InstanceResult, ...]
    error: str | None


# ---------------------------------------------------------------------------
# Sender
# ---------------------------------------------------------------------------


class Sender:
    """DICOM transport operations for Sender Lite."""

    def __init__(self, config: Config, logger: SenderLogger) -> None:
        self.config = config
        self.logger = logger

    # ------------------------------------------------------------------ echo
    def echo(self) -> EchoResult:
        """Run a single C-ECHO against the configured peer."""
        if pynetdicom is None:
            return EchoResult(
                success=False,
                status=None,
                duration=0.0,
                error="pynetdicom unavailable",
            )

        started = time.monotonic()
        ae = pynetdicom.AE(ae_title=self.config.calling_ae)
        ae.connection_timeout = self.config.connect_timeout
        ae.acse_timeout = self.config.connect_timeout
        ae.dimse_timeout = self.config.dimse_timeout
        ae.network_timeout = self.config.dimse_timeout
        ae.add_requested_context(Verification)

        assoc = None
        try:
            assoc = ae.associate(
                self.config.host,
                self.config.port,
                ae_title=self.config.called_ae,
                max_pdu=self.config.max_pdu,
            )
            if not assoc.is_established:
                duration = time.monotonic() - started
                return EchoResult(
                    success=False,
                    status=None,
                    duration=duration,
                    error=_classify_establishment_failure(assoc),
                )

            response = assoc.send_c_echo()
            duration = time.monotonic() - started
            status_code = _read_status(response)
            success = status_code == 0x0000
            if assoc.is_established:
                assoc.release()
            return EchoResult(
                success=success,
                status=status_code,
                duration=duration,
                error=None if success else f"echo status 0x{status_code or 0:04X}",
            )
        except Exception as exc:  # noqa: BLE001  -- echo top-level guard per plan §12
            duration = time.monotonic() - started
            return EchoResult(
                success=False,
                status=None,
                duration=duration,
                error=str(exc),
            )
        finally:
            if assoc is not None and assoc.is_established:
                with contextlib.suppress(Exception):
                    assoc.release()

    # ------------------------------------------------------------- send_study
    def send_study(self, study: StudyBatch, cancel_event: threading.Event) -> StudyResult:
        """Send one Study Batch over a single association."""
        started = time.monotonic()
        instances = study.instances
        self.logger.info(
            "study_started",
            study_uid=study.study_uid,
            instance_count=len(instances),
        )

        # Preflight: >128 contexts -> fail all without network
        pairs = sorted(study.presentation_requirements, key=lambda p: (p[0], p[1]))
        if len(pairs) > 128:
            failed = tuple(
                _failed_instance(
                    inst,
                    reason="presentation_context_limit",
                    duration=time.monotonic() - started,
                )
                for inst in instances
            )
            duration = time.monotonic() - started
            self.logger.error(
                "study_completed",
                study_uid=study.study_uid,
                attempted=len(instances),
                succeeded=0,
                warned=0,
                failed=len(instances),
                cancelled=0,
                duration=round(duration, 3),
            )
            return StudyResult(
                study_uid=study.study_uid,
                attempted=len(instances),
                succeeded=0,
                warned=0,
                failed=len(instances),
                cancelled=0,
                duration=duration,
                instances=failed,
                error="presentation_context_limit",
            )

        if pynetdicom is None:
            failed = tuple(
                _failed_instance(
                    inst,
                    reason="pynetdicom unavailable",
                    duration=time.monotonic() - started,
                )
                for inst in instances
            )
            return _study_result(study.study_uid, failed, started)

        ae = pynetdicom.AE(ae_title=self.config.calling_ae)
        ae.connection_timeout = self.config.connect_timeout
        ae.acse_timeout = self.config.connect_timeout
        ae.dimse_timeout = self.config.dimse_timeout
        ae.network_timeout = self.config.dimse_timeout
        for sop_class, transfer_syntax in pairs:
            ae.add_requested_context(sop_class, transfer_syntax)

        assoc = None
        try:
            assoc = ae.associate(
                self.config.host,
                self.config.port,
                ae_title=self.config.called_ae,
                max_pdu=self.config.max_pdu,
            )
            if not assoc.is_established:
                reason = _classify_establishment_failure(assoc)
                self.logger.error(
                    "association_rejected",
                    study_uid=study.study_uid,
                    reason=reason,
                )
                failed = tuple(
                    _failed_instance(inst, reason=reason, duration=time.monotonic() - started)
                    for inst in instances
                )
                return _study_result(study.study_uid, failed, started)

            accepted = _accepted_contexts(assoc)
            rejected_pairs = _rejected_context_pairs(assoc)
            self.logger.info(
                "association_accepted",
                study_uid=study.study_uid,
                accepted=len(accepted),
            )
            for sop_class, transfer_syntax in rejected_pairs:
                self.logger.warning(
                    "presentation_context_rejected",
                    study_uid=study.study_uid,
                    sop_class_uid=sop_class,
                    transfer_syntax_uid=transfer_syntax,
                )

            results: list[InstanceResult] = []
            message_id = 1
            association_usable = True

            for inst in instances:
                key = (inst.sop_class_uid, inst.transfer_syntax_uid)
                if key not in accepted:
                    results.append(
                        _failed_instance(
                            inst,
                            reason="context_rejected",
                            duration=time.monotonic() - started,
                        )
                    )
                    continue
                if cancel_event.is_set():
                    results.append(_cancelled_instance(inst, time.monotonic() - started))
                    continue

                if not association_usable:
                    results.append(
                        _failed_instance(
                            inst,
                            reason="association_lost",
                            duration=time.monotonic() - started,
                        )
                    )
                    continue

                # Revalidation
                reval_failure = _revalidate(inst)
                if reval_failure is not None:
                    self.logger.error(
                        "instance_failed",
                        study_uid=study.study_uid,
                        sop_instance_uid=inst.sop_instance_uid,
                        reason=reval_failure,
                    )
                    results.append(
                        _failed_instance(
                            inst,
                            reason=reval_failure,
                            duration=time.monotonic() - started,
                        )
                    )
                    continue

                # C-STORE
                inst_started = time.monotonic()
                try:
                    ds = dcmread(inst.path, force=False)
                    response = assoc.send_c_store(ds, msg_id=message_id)
                    message_id = (message_id % 65535) + 1
                    duration = time.monotonic() - inst_started
                    status_code = _read_status(response)
                    if status_code is None:
                        results.append(
                            _failed_instance(inst, reason="no_response", duration=duration)
                        )
                        if not _assoc_usable(assoc):
                            association_usable = False
                            self.logger.error(
                                "association_aborted",
                                study_uid=study.study_uid,
                                reason="association_lost",
                            )
                        continue
                    if status_code == 0x0000:
                        self.logger.info(
                            "instance_sent",
                            study_uid=study.study_uid,
                            sop_instance_uid=inst.sop_instance_uid,
                            duration=round(duration, 3),
                        )
                        results.append(
                            InstanceResult(
                                sop_instance_uid=inst.sop_instance_uid,
                                sop_class_uid=inst.sop_class_uid,
                                transfer_syntax_uid=inst.transfer_syntax_uid,
                                path=inst.path,
                                size_bytes=inst.size_bytes,
                                status="success",
                                status_code=status_code,
                                reason=None,
                                duration=duration,
                            )
                        )
                    elif 0xB000 <= status_code <= 0xBFFF:
                        self.logger.warning(
                            "instance_warning",
                            study_uid=study.study_uid,
                            sop_instance_uid=inst.sop_instance_uid,
                            status=f"0x{status_code:04X}",
                            duration=round(duration, 3),
                        )
                        results.append(
                            InstanceResult(
                                sop_instance_uid=inst.sop_instance_uid,
                                sop_class_uid=inst.sop_class_uid,
                                transfer_syntax_uid=inst.transfer_syntax_uid,
                                path=inst.path,
                                size_bytes=inst.size_bytes,
                                status="warning",
                                status_code=status_code,
                                reason=None,
                                duration=duration,
                            )
                        )
                    else:
                        self.logger.error(
                            "instance_failed",
                            study_uid=study.study_uid,
                            sop_instance_uid=inst.sop_instance_uid,
                            status=f"0x{status_code:04X}",
                        )
                        results.append(
                            InstanceResult(
                                sop_instance_uid=inst.sop_instance_uid,
                                sop_class_uid=inst.sop_class_uid,
                                transfer_syntax_uid=inst.transfer_syntax_uid,
                                path=inst.path,
                                size_bytes=inst.size_bytes,
                                status="failure",
                                status_code=status_code,
                                reason=f"status 0x{status_code:04X}",
                                duration=duration,
                            )
                        )
                        if not _assoc_usable(assoc):
                            association_usable = False
                            self.logger.error(
                                "association_aborted",
                                study_uid=study.study_uid,
                                reason="association_lost",
                            )
                except Exception as exc:  # noqa: BLE001  -- per-instance failure continuation per plan §10.7
                    duration = time.monotonic() - inst_started
                    self.logger.error(
                        "instance_failed",
                        study_uid=study.study_uid,
                        sop_instance_uid=inst.sop_instance_uid,
                        error=str(exc),
                    )
                    results.append(_failed_instance(inst, reason=str(exc), duration=duration))
                    if not _assoc_usable(assoc):
                        association_usable = False
                        self.logger.error(
                            "association_aborted",
                            study_uid=study.study_uid,
                            reason="association_lost",
                        )

            # Teardown
            if cancel_event.is_set() or not association_usable:
                if assoc.is_established:
                    with contextlib.suppress(Exception):
                        assoc.abort()
                self.logger.error(
                    "association_aborted",
                    study_uid=study.study_uid,
                    reason="cancelled" if cancel_event.is_set() else "unusable",
                )
            else:
                try:
                    assoc.release()
                except Exception:  # noqa: BLE001  -- release failed; best-effort abort in teardown
                    with contextlib.suppress(Exception):
                        assoc.abort()

            final = _study_result(study.study_uid, tuple(results), started)
            self.logger.info(
                "study_completed",
                study_uid=study.study_uid,
                attempted=final.attempted,
                succeeded=final.succeeded,
                warned=final.warned,
                failed=final.failed,
                cancelled=final.cancelled,
                duration=round(final.duration, 3),
            )
            return final
        except Exception as exc:  # noqa: BLE001  -- send_study top-level guard per plan §10.6/§16
            failed = tuple(
                _failed_instance(inst, reason=str(exc), duration=time.monotonic() - started)
                for inst in instances
            )
            return _study_result(study.study_uid, failed, started)
        finally:
            if assoc is not None and assoc.is_established:
                with contextlib.suppress(Exception):
                    assoc.release()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_status(response: Any) -> int | None:
    if response is None:
        return None
    status = getattr(response, "Status", None)
    if status is None:
        return None
    try:
        return int(status)
    except (TypeError, ValueError):
        return None


def _classify_establishment_failure(assoc: Any) -> str:
    if assoc is None:
        return "association_failed"
    if getattr(assoc, "is_aborted", False):
        return "association_aborted"
    if getattr(assoc, "is_rejected", False):
        return "association_rejected"
    return "association_failed"


def _accepted_contexts(assoc: Any) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for cx in getattr(assoc, "accepted_contexts", []) or []:
        abstract = str(getattr(cx, "abstract_syntax", ""))
        ts_raw = getattr(cx, "transfer_syntax", None)
        if isinstance(ts_raw, list):
            for t in ts_raw:
                if abstract and t:
                    out.add((abstract, str(t)))
        else:
            ts = str(ts_raw) if ts_raw is not None else ""
            if abstract and ts:
                out.add((abstract, ts))
    return out


def _rejected_context_pairs(assoc: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for cx in getattr(assoc, "rejected_contexts", []) or []:
        abstract = str(getattr(cx, "abstract_syntax", ""))
        ts = getattr(cx, "transfer_syntax", None)
        if isinstance(ts, list):
            for t in ts:
                out.append((abstract, str(t)))
        elif ts is not None:
            out.append((abstract, str(ts)))
    return out


def _assoc_usable(assoc: Any) -> bool:
    return bool(
        getattr(assoc, "is_established", False)
        and not getattr(assoc, "is_aborted", False)
        and not getattr(assoc, "is_released", False)
    )


def _revalidate(inst: CatalogInstance) -> str | None:
    path = inst.path
    if not path.exists():
        return "file_missing"
    if path.is_symlink():
        return "file_symlink"
    try:
        ds = dcmread(path, force=False)
    except Exception as exc:  # noqa: BLE001  -- revalidation read per plan §10.4
        return f"read_failed: {exc}"
    try:
        if str(getattr(ds, "StudyInstanceUID", "")) != inst.study_uid:
            return "study_uid_changed"
        if str(getattr(ds, "SeriesInstanceUID", "")) != inst.series_uid:
            return "series_uid_changed"
        if str(getattr(ds, "SOPInstanceUID", "")) != inst.sop_instance_uid:
            return "sop_instance_uid_changed"
        if str(getattr(ds, "SOPClassUID", "")) != inst.sop_class_uid:
            return "sop_class_uid_changed"
        file_meta = getattr(ds, "file_meta", None)
        if file_meta is None:
            return "file_meta_missing"
        if str(getattr(file_meta, "TransferSyntaxUID", "")) != inst.transfer_syntax_uid:
            return "transfer_syntax_changed"
    except (AttributeError, ValueError) as exc:
        return f"uid_check_failed: {exc}"
    return None


def _failed_instance(inst: CatalogInstance, reason: str, duration: float) -> InstanceResult:
    return InstanceResult(
        sop_instance_uid=inst.sop_instance_uid,
        sop_class_uid=inst.sop_class_uid,
        transfer_syntax_uid=inst.transfer_syntax_uid,
        path=inst.path,
        size_bytes=inst.size_bytes,
        status="failure",
        status_code=None,
        reason=reason,
        duration=duration,
    )


def _cancelled_instance(inst: CatalogInstance, duration: float) -> InstanceResult:
    return InstanceResult(
        sop_instance_uid=inst.sop_instance_uid,
        sop_class_uid=inst.sop_class_uid,
        transfer_syntax_uid=inst.transfer_syntax_uid,
        path=inst.path,
        size_bytes=inst.size_bytes,
        status="cancelled",
        status_code=None,
        reason="cancelled",
        duration=duration,
    )


def _study_result(
    study_uid: str, instances: tuple[InstanceResult, ...], started: float
) -> StudyResult:
    duration = time.monotonic() - started
    succeeded = sum(1 for i in instances if i.status == "success")
    warned = sum(1 for i in instances if i.status == "warning")
    failed = sum(1 for i in instances if i.status == "failure")
    cancelled = sum(1 for i in instances if i.status == "cancelled")
    error: str | None = None
    if failed and not succeeded and not warned:
        error = instances[0].reason if instances else None
    return StudyResult(
        study_uid=study_uid,
        attempted=len(instances),
        succeeded=succeeded,
        warned=warned,
        failed=failed,
        cancelled=cancelled,
        duration=duration,
        instances=instances,
        error=error,
    )
