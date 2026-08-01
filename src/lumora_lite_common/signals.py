# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Portable signal handler install/restore for the Lumora Lite CLIs.

CPython only permits signal registration from the main thread, and the set of
installable signals differs by platform. Both Lite CLIs need the same portable
scaffolding (iterate ``SIGINT``/``SIGTERM``/``SIGBREAK`` where available, tolerate
signals that exist but cannot be installed, and remember previous handlers for
restoration in a ``finally``). What differs is only the per-signal callback:
Probe sets a shutdown event; Sender counts signals and escalates to exit 130 on
the second.

Rather than wrap this in a stateful class, the two helpers below take the
caller's callback as an argument. ``on_signal`` receives the signal number and
its resolved name and decides what to do (set an event, raise SystemExit, log,
etc.). See ADR-0028.
"""

from __future__ import annotations

import signal
import threading
from collections.abc import Callable
from typing import Any

# Signals both tools try to install, in priority order. Availability is checked
# per-platform via getattr, so unknown names are skipped rather than fatal.
_SIGNAL_NAMES = ("SIGINT", "SIGTERM", "SIGBREAK")


def install_signal_handlers(
    on_signal: Callable[[int, object], None],
) -> dict[int, Any]:
    """Install ``on_signal`` for each installable signal; return prior handlers.

    Must be called from the main thread. Returns a mapping of signal number to
    the previous handler (suitable for passing to :func:`restore_signal_handlers`).
    If the caller is not on the main thread, returns an empty dict and installs
    nothing.
    """
    if threading.current_thread() is not threading.main_thread():
        return {}

    def handler(signum: int, _frame: object) -> None:
        try:
            name = signal.Signals(signum).name
        except (AttributeError, ValueError):
            name = str(signum)
        on_signal(signum, name)

    previous_handlers: dict[int, Any] = {}
    for signal_name in _SIGNAL_NAMES:
        signal_number = getattr(signal, signal_name, None)
        if signal_number is None:
            continue
        try:
            previous_handlers[signal_number] = signal.getsignal(signal_number)
            signal.signal(signal_number, handler)
        except (OSError, ValueError):
            # Some signals are exposed by a platform but cannot be installed.
            previous_handlers.pop(signal_number, None)
    return previous_handlers


def restore_signal_handlers(previous_handlers: dict[int, Any]) -> None:
    """Restore the handlers captured by :func:`install_signal_handlers`.

    Best-effort: restoration errors are swallowed so they never mask the tool's
    own shutdown result.
    """
    for signal_number, handler in previous_handlers.items():
        try:
            signal.signal(signal_number, handler)
        except (OSError, ValueError):
            pass
