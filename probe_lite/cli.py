"""The ``probe-lite`` command-line entry point."""

from __future__ import annotations

import signal
import sys
import threading
from typing import Any

from .config import parse_args
from .log import ProbeLogger
from .receiver import ProbeReceiver


def _install_signal_handlers(stop_event: threading.Event, logger: ProbeLogger) -> dict[int, Any]:
    """Install portable shutdown handlers and return the previous handlers.

    CPython only permits signal registration from the main thread, and the set of
    installable signals differs by platform. Probe Lite treats both constraints as
    capabilities instead of assuming POSIX signal behavior.
    """
    if threading.current_thread() is not threading.main_thread():
        return {}

    def request_stop(signum: int, _frame: object) -> None:
        try:
            name = signal.Signals(signum).name
        except (AttributeError, ValueError):
            name = str(signum)
        logger.info("shutdown_requested", signal=name)
        stop_event.set()

    previous_handlers: dict[int, Any] = {}
    for signal_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        signal_number = getattr(signal, signal_name, None)
        if signal_number is None:
            continue
        try:
            previous_handlers[signal_number] = signal.getsignal(signal_number)
            signal.signal(signal_number, request_stop)
        except (OSError, ValueError):
            # Some signals are exposed by a platform but cannot be installed.
            previous_handlers.pop(signal_number, None)
    return previous_handlers


def _restore_signal_handlers(previous_handlers: dict[int, Any]) -> None:
    for signal_number, handler in previous_handlers.items():
        try:
            signal.signal(signal_number, handler)
        except (OSError, ValueError):
            # Restoration should not mask the receiver's shutdown result.
            pass


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
        _restore_signal_handlers(previous_handlers)
    return 0
