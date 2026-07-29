from __future__ import annotations

import signal
import threading
from io import StringIO

from probe_lite import cli
from probe_lite.log import ProbeLogger


def test_signal_handlers_are_portable_and_restorable() -> None:
    stop_event = threading.Event()
    logger = ProbeLogger("json", stream=StringIO())
    previous = cli._install_signal_handlers(stop_event, logger)
    try:
        assert signal.SIGINT in previous
        handler = signal.getsignal(signal.SIGINT)
        assert callable(handler)
        handler(signal.SIGINT, None)
        assert stop_event.is_set()
    finally:
        cli.restore_signal_handlers(previous)


def test_signal_registration_is_skipped_outside_main_thread() -> None:
    result: list[dict[int, object]] = []
    stop_event = threading.Event()
    logger = ProbeLogger("json", stream=StringIO())

    thread = threading.Thread(
        target=lambda: result.append(cli._install_signal_handlers(stop_event, logger))
    )
    thread.start()
    thread.join()

    assert result == [{}]


def test_keyboard_interrupt_still_stops_receiver(monkeypatch) -> None:
    calls: list[str] = []

    class FakeReceiver:
        def __init__(self, config, logger) -> None:
            del config, logger

        def serve(self, stop_event) -> None:
            del stop_event
            raise KeyboardInterrupt

        def stop(self) -> None:
            calls.append("stop")

    monkeypatch.setattr(cli, "ProbeReceiver", FakeReceiver)
    monkeypatch.setattr(cli, "_install_signal_handlers", lambda stop_event, logger: {})

    assert cli.main(["--port", "11113"]) == 0
    assert calls == ["stop"]
