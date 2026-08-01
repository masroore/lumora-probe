# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""The ``probe-lite`` command-line entry point."""

from __future__ import annotations

import sys
import threading
from typing import Any

from lumora_lite_common.signals import install_signal_handlers, restore_signal_handlers

from .config import parse_args
from .log import ProbeLogger
from .receiver import ProbeReceiver


def _install_signal_handlers(stop_event: threading.Event, logger: ProbeLogger) -> dict[int, Any]:
    """Install portable shutdown handlers and return the previous handlers.

    The install/restore scaffolding is shared; only Probe Lite's single-shot
    "set the stop event" callback is defined here. See ADR-0028.
    """

    def request_stop(_signum: int, name: object) -> None:
        logger.info("shutdown_requested", signal=name)
        stop_event.set()

    return install_signal_handlers(request_stop)


def main(argv: list[str] | None = None) -> int:
    try:
        config = parse_args(argv)
    except ValueError as exc:
        print(f"probe-lite: configuration error: {exc}", file=sys.stdout, flush=True)
        return 2

    logger = ProbeLogger(config.log_format)
    receiver = ProbeReceiver(config, logger=logger)
    stop_event = threading.Event()
    previous_handlers = _install_signal_handlers(stop_event, logger)

    try:
        receiver.serve(stop_event)
    except KeyboardInterrupt:
        # Covers embedded/non-main-thread callers where signal registration is not
        # available, while still guaranteeing the same clean receiver shutdown.
        logger.info("shutdown_requested", signal="KeyboardInterrupt")
        receiver.stop()
    except OSError as exc:
        logger.error("startup_failed", port=config.port, error=str(exc))
        return 1
    except RuntimeError as exc:
        logger.error("startup_failed", error=str(exc))
        return 1
    finally:
        restore_signal_handlers(previous_handlers)
    return 0
