"""The ``probe-lite`` command-line entry point."""

from __future__ import annotations

import signal
import sys
import threading

from .config import parse_args
from .log import ProbeLogger
from .receiver import ProbeReceiver


def main(argv: list[str] | None = None) -> int:
    try:
        config = parse_args(argv)
    except ValueError as exc:
        print(f"probe-lite: configuration error: {exc}", file=sys.stdout, flush=True)
        return 2

    logger = ProbeLogger(config.log_format)
    receiver = ProbeReceiver(config, logger=logger)
    stop_event = threading.Event()

    def request_stop(signum: int, _frame: object) -> None:
        logger.info("shutdown_requested", signal=signal.Signals(signum).name)
        stop_event.set()

    previous_handlers: dict[int, signal.Handlers] = {}
    for signal_number in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signal_number] = signal.getsignal(signal_number)
        signal.signal(signal_number, request_stop)

    try:
        receiver.serve(stop_event)
    except OSError as exc:
        logger.error("startup_failed", port=config.port, error=str(exc))
        return 1
    except RuntimeError as exc:
        logger.error("startup_failed", error=str(exc))
        return 1
    finally:
        for signal_number, handler in previous_handlers.items():
            signal.signal(signal_number, handler)
    return 0
