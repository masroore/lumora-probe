# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""The ``sender-lite`` command-line entry point."""

from __future__ import annotations

import sys
import threading
import time
from typing import Any

from lumora_lite_common.signals import install_signal_handlers, restore_signal_handlers

from .catalog import REASON_CONFLICT, CatalogError, build_catalog
from .config import parse_args
from .log import SenderLogger
from .sender import Sender


def _install_signal_handlers(cancel_event: threading.Event, logger: SenderLogger) -> dict[int, Any]:
    """Install portable cancellation handlers and return previous handlers.

    First signal sets the cancel event and logs ``cancellation_requested``.
    Subsequent signals raise ``SystemExit(130)`` for immediate termination.
    """
    call_count = {"n": 0}

    def request_cancel(_signum: int, name: object) -> None:
        call_count["n"] += 1
        if call_count["n"] == 1:
            logger.warning("cancellation_requested", signal=name)
            cancel_event.set()
        else:
            raise SystemExit(130)

    return install_signal_handlers(request_cancel)


def main(argv: list[str] | None = None) -> int:
    try:
        config = parse_args(argv)
    except ValueError as exc:
        print(f"sender-lite: configuration error: {exc}", file=sys.stdout, flush=True)
        return 2

    logger = SenderLogger(config.log_format)
    mode = "echo" if config.echo else "send"
    logger.info(
        "configuration_resolved",
        mode=mode,
        config_path=config.config_path,
        input=config.input,
        host=config.host,
        port=config.port,
        calling_ae=config.calling_ae,
        called_ae=config.called_ae,
        study_delay=config.study_delay,
        connect_timeout=config.connect_timeout,
        dimse_timeout=config.dimse_timeout,
        max_pdu=config.max_pdu,
        log_format=config.log_format,
        verbose=config.verbose,
    )

    cancel_event = threading.Event()
    previous_handlers = _install_signal_handlers(cancel_event, logger)
    sender = Sender(config, logger)
    run_started = time.monotonic()
    exit_code = 0
    run_failed_reason: str | None = None
    run_failed_error: str | None = None

    try:
        if config.echo:
            exit_code = _run_echo(sender, logger, config)
        else:
            exit_code, run_failed_reason, run_failed_error = _run_send(
                sender, logger, config, cancel_event, run_started
            )
    except KeyboardInterrupt:
        logger.warning("cancellation_requested", signal="KeyboardInterrupt")
        exit_code = 130
    except Exception as exc:  # noqa: BLE001
        run_failed_reason = "unexpected_error"
        run_failed_error = str(exc)
        exit_code = 1
    finally:
        restore_signal_handlers(previous_handlers)
        _emit_final_summary(logger, exit_code, run_failed_reason, run_failed_error, run_started)

    return exit_code


def _run_echo(sender: Sender, logger: SenderLogger, config: Any) -> int:
    result = sender.echo()
    status_hex = f"0x{result.status:04X}" if result.status is not None else None
    level = "INFO" if result.success else "ERROR"
    logger.event(
        "echo_completed",
        level,
        peer=f"{config.host}:{config.port}",
        status=status_hex,
        duration=result.duration,
    )
    exit_code = 0 if result.success else 1
    logger.event(
        "run_completed",
        "INFO" if exit_code == 0 else "ERROR",
        mode="echo",
        duration=result.duration,
        exit_code=exit_code,
    )
    return exit_code


def _run_send(
    sender: Sender,
    logger: SenderLogger,
    config: Any,
    cancel_event: threading.Event,
    run_started: float,
) -> tuple[int, str | None, str | None]:
    logger.info("scan_started", input=config.input)
    scan_started = time.monotonic()
    try:
        catalog = build_catalog(config.input)
    except CatalogError as exc:
        return 1, "catalog_error", str(exc)

    for issue in catalog.issues:
        if issue.reason == REASON_CONFLICT:
            logger.error(
                "catalog_conflict",
                path=issue.path,
                sop_instance_uid=issue.sop_instance_uid,
                reason=issue.reason,
            )
        else:
            logger.warning(
                "file_skipped",
                path=issue.path,
                reason=issue.reason,
                error=issue.message,
            )

    scan_duration = time.monotonic() - scan_started
    logger.info(
        "scan_completed",
        scanned=catalog.scanned_count,
        rejected=catalog.rejected_count,
        studies=catalog.study_count,
        series=catalog.series_count,
        instances=catalog.sendable_count,
        bytes=catalog.total_bytes,
        duration=scan_duration,
    )

    if catalog.sendable_count == 0:
        return 1, "empty_catalog", None

    study_results = []
    studies = catalog.studies
    total_studies = len(studies)
    for idx, study in enumerate(studies):
        if cancel_event.is_set():
            break
        result = sender.send_study(study, cancel_event, ordinal=idx + 1, total=total_studies)
        study_results.append(result)
        if idx < len(studies) - 1 and not cancel_event.is_set():
            next_study_uid = studies[idx + 1].study_uid
            logger.info(
                "study_delay_started",
                seconds=config.study_delay,
                next_study_uid=next_study_uid,
            )
            cancel_event.wait(timeout=config.study_delay)

    total_attempted = sum(r.attempted for r in study_results)
    total_succeeded = sum(r.succeeded for r in study_results)
    total_warned = sum(r.warned for r in study_results)
    total_failed = sum(r.failed for r in study_results)
    total_cancelled = sum(r.cancelled for r in study_results)
    run_duration = time.monotonic() - run_started

    if cancel_event.is_set():
        exit_code = 130
    elif total_failed > 0:
        exit_code = 1
    else:
        exit_code = 0

    level = "INFO" if exit_code == 0 else "ERROR"
    logger.event(
        "run_completed",
        level,
        studies=len(study_results),
        attempted=total_attempted,
        succeeded=total_succeeded,
        warned=total_warned,
        failed=total_failed,
        cancelled=total_cancelled,
        duration=run_duration,
        exit_code=exit_code,
    )
    return exit_code, None, None


def _emit_final_summary(
    logger: SenderLogger,
    exit_code: int,
    run_failed_reason: str | None,
    run_failed_error: str | None,
    run_started: float,
) -> None:
    if run_failed_reason is not None:
        logger.error(
            "run_failed",
            reason=run_failed_reason,
            error=run_failed_error,
            exit_code=exit_code,
        )
