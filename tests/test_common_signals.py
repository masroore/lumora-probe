# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Tests for the shared signal install/restore helpers.

The plumbing is shared; each Lite tool supplies its own callback. These tests
cover both the single-shot (Probe-style) and escalating (Sender-style) callbacks
against the same shared functions.
"""

from __future__ import annotations

import signal
import threading

import pytest

from lumora_lite_common.signals import install_signal_handlers, restore_signal_handlers


def _previous_sigint() -> object:
    return signal.getsignal(signal.SIGINT)


def test_install_registers_handler_and_returns_previous() -> None:
    before = _previous_sigint()
    try:
        previous = install_signal_handlers(lambda _s, _n: None)
        assert signal.SIGINT in previous
        assert previous[signal.SIGINT] is before
        assert signal.getsignal(signal.SIGINT) is not before
    finally:
        signal.signal(signal.SIGINT, before)


def test_restore_returns_previous_handler() -> None:
    before = _previous_sigint()
    previous = install_signal_handlers(lambda _s, _n: None)
    try:
        restore_signal_handlers(previous)
        assert signal.getsignal(signal.SIGINT) is before
    finally:
        # restore_signal_handlers already restored, but guard against partial runs
        signal.signal(signal.SIGINT, before)


def test_single_shot_callback_runs_on_signal() -> None:
    before = _previous_sigint()
    fired: list[object] = []
    previous = install_signal_handlers(lambda signum, name: fired.append((signum, name)))
    try:
        handler = signal.getsignal(signal.SIGINT)
        assert callable(handler)
        handler(signal.SIGINT, None)
        assert len(fired) == 1
        assert fired[0][0] == signal.SIGINT
        assert fired[0][1] == "SIGINT"
    finally:
        restore_signal_handlers(previous)
        signal.signal(signal.SIGINT, before)


def test_escalating_callback_terminates_on_second_signal() -> None:
    before = _previous_sigint()
    count = {"n": 0}

    def escalating(_signum: int, _name: object) -> None:
        count["n"] += 1
        if count["n"] >= 2:
            raise SystemExit(130)

    previous = install_signal_handlers(escalating)
    try:
        handler = signal.getsignal(signal.SIGINT)
        handler(signal.SIGINT, None)  # first: no raise
        assert count["n"] == 1
        with pytest.raises(SystemExit) as exc:
            handler(signal.SIGINT, None)  # second: escalate
        assert exc.value.code == 130
    finally:
        restore_signal_handlers(previous)
        signal.signal(signal.SIGINT, before)


def test_install_skipped_outside_main_thread() -> None:
    result: list[dict[int, object]] = []
    thread = threading.Thread(
        target=lambda: result.append(install_signal_handlers(lambda _s, _n: None))
    )
    thread.start()
    thread.join()
    assert result == [{}]


def test_restore_is_best_effort() -> None:
    # Restoring an invalid entry should not raise; restoration failures are swallowed.
    restore_signal_handlers({9999: lambda *a: None})
