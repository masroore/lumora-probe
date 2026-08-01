# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

from pathlib import Path

import pytest

from probe_lite import cli
from probe_lite.config import (
    DEFAULT_AE_TITLE,
    DEFAULT_MAX_PDU,
    DEFAULT_PORT,
    build_parser,
    parse_args,
)


def test_defaults() -> None:
    config = parse_args([], {})

    assert config.port == DEFAULT_PORT
    assert config.ae_title == DEFAULT_AE_TITLE
    assert config.output == Path("storage/inbox")
    assert config.accept_ae is None
    assert config.log_format == "text"
    assert config.max_pdu == DEFAULT_MAX_PDU
    assert config.verbose is False


def test_help_mentions_operational_options_and_security_warning() -> None:
    help_text = build_parser().format_help()

    for option in (
        "--port",
        "--ae",
        "--output",
        "--accept-ae",
        "--format",
        "--max-pdu",
        "--verbose",
    ):
        assert option in help_text
    assert "No security. Use on trusted networks only." in help_text


def test_environment_values_are_used() -> None:
    config = parse_args(
        [],
        {
            "PROBE_LITE_PORT": "12000",
            "PROBE_LITE_AE": "TEST_SCP",
            "PROBE_LITE_OUTPUT": "/tmp/dicom",
            "PROBE_LITE_ACCEPT_AE": "ONE, TWO",
            "PROBE_LITE_FORMAT": "json",
            "PROBE_LITE_MAX_PDU": "8192",
            "PROBE_LITE_VERBOSE": "true",
        },
    )

    assert config.port == 12000
    assert config.ae_title == "TEST_SCP"
    assert config.output == Path("/tmp/dicom")
    assert config.accept_ae == frozenset({"ONE", "TWO"})
    assert config.log_format == "json"
    assert config.max_pdu == 8192
    assert config.verbose is True


def test_cli_values_override_environment() -> None:
    config = parse_args(
        ["--port", "12001", "--ae", "CLI_SCP", "--format", "text", "--max-pdu", "4096", "-v"],
        {
            "PROBE_LITE_PORT": "12000",
            "PROBE_LITE_AE": "ENV_SCP",
            "PROBE_LITE_FORMAT": "json",
            "PROBE_LITE_MAX_PDU": "8192",
            "PROBE_LITE_VERBOSE": "false",
        },
    )

    assert config.port == 12001
    assert config.ae_title == "CLI_SCP"
    assert config.log_format == "text"
    assert config.max_pdu == 4096
    assert config.verbose is True


@pytest.mark.parametrize("arguments", [["--port", "0"], ["--max-pdu", "0"], ["--ae", "é"]])
def test_invalid_values_are_rejected(arguments: list[str]) -> None:
    with pytest.raises(ValueError):
        parse_args(arguments, {})


def test_port_binding_error_returns_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FailingReceiver:
        def __init__(self, config: object, logger: object) -> None:
            pass

        def serve(self, stop_event: object) -> None:
            raise OSError("address already in use")

    monkeypatch.setattr(cli, "ProbeReceiver", FailingReceiver)
    assert cli.main([]) == 1
    assert "Startup Failed" in capsys.readouterr().out
