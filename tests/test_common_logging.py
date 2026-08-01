# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Tests for the shared event-logger engine (`lumora_lite_common.logging`)."""

from __future__ import annotations

import io
import json
from typing import ClassVar

import pytest

from lumora_lite_common.logging import EventLogger, _text_value


class _DemoLogger(EventLogger):
    """Minimal subclass exercising the TEXT_LABELS override hook."""

    TEXT_LABELS: ClassVar[dict[str, str]] = {"demo": "Demo Event"}


def test_invalid_log_format_raises() -> None:
    with pytest.raises(ValueError, match="log_format"):
        EventLogger("xml", io.StringIO())


def test_defaults_to_stdout() -> None:
    logger = EventLogger("text")
    import sys

    assert logger.stream is sys.stdout


def test_json_event_shape_and_flush() -> None:
    output = io.StringIO()
    _DemoLogger("json", output).info("demo", uid="1.2.3", count=2)

    record = json.loads(output.getvalue())
    assert record["level"] == "INFO"
    assert record["event"] == "demo"
    assert record["uid"] == "1.2.3"
    assert record["count"] == 2
    assert record["timestamp"].endswith("Z")


def test_json_uses_default_str_for_pathlike() -> None:
    from pathlib import Path

    output = io.StringIO()
    _DemoLogger("json", output).info("demo", path=Path("/tmp/x"))

    record = json.loads(output.getvalue())
    assert record["path"] == "/tmp/x"


def test_text_event_uses_label_map_and_uppercase_keys() -> None:
    output = io.StringIO()
    _DemoLogger("text", output).info("demo", uid="1.2.3")

    line = output.getvalue()
    assert "[INFO] Demo Event" in line
    assert "UID=1.2.3" in line


def test_text_event_falls_back_to_title_cased_name() -> None:
    output = io.StringIO()
    _DemoLogger("text", output).info("not_in_map")

    assert "Not In Map" in output.getvalue()


def test_text_value_joins_iterables() -> None:
    assert _text_value([1, 2, 3]) == "1,2,3"
    assert _text_value((1, 2)) == "1,2"
    assert _text_value("plain") == "plain"
    assert _text_value("a\nb") == "a\\nb"


def test_warning_and_error_levels() -> None:
    output = io.StringIO()
    logger = _DemoLogger("json", output)
    logger.warning("demo", x=1)
    logger.error("demo", x=2)

    lines = [ln for ln in output.getvalue().splitlines() if ln]
    assert json.loads(lines[0])["level"] == "WARNING"
    assert json.loads(lines[1])["level"] == "ERROR"


def test_each_json_event_is_one_line() -> None:
    output = io.StringIO()
    logger = _DemoLogger("json", output)
    logger.info("demo", a=1)
    logger.error("demo", b=2)

    lines = [ln for ln in output.getvalue().split("\n") if ln]
    assert len(lines) == 2
    for line in lines:
        assert line.count("\n") == 0
