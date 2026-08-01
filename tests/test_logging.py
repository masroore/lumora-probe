# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

import io
import json

from probe_lite.log import ProbeLogger


def test_json_logging_is_jsonl() -> None:
    output = io.StringIO()
    ProbeLogger("json", output).info("instance_received", sop_instance_uid="1.2.3", size_bytes=12)

    record = json.loads(output.getvalue())
    assert record["level"] == "INFO"
    assert record["event"] == "instance_received"
    assert record["sop_instance_uid"] == "1.2.3"
    assert record["size_bytes"] == 12
    assert record["timestamp"].endswith("Z")


def test_text_logging_is_one_line() -> None:
    output = io.StringIO()
    ProbeLogger("text", output).info("association_accepted", calling_ae="SENDER", contexts=3)

    line = output.getvalue()
    assert line.count("\n") == 1
    assert "[INFO] Association accepted" in line
    assert "CALLING_AE=SENDER" in line
    assert "CONTEXTS=3" in line
