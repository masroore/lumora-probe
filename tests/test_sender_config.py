"""Tests for Sender Lite configuration resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from sender_lite.config import (
    DEFAULT_CALLED_AE,
    DEFAULT_CALLING_AE,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_DIMSE_TIMEOUT,
    DEFAULT_HOST,
    DEFAULT_LOG_FORMAT,
    DEFAULT_MAX_PDU,
    DEFAULT_PORT,
    DEFAULT_STUDY_DELAY,
    build_parser,
    parse_args,
)


def _write_toml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_defaults_with_explicit_input(tmp_path: Path) -> None:
    input_dir = tmp_path / "dicom"
    input_dir.mkdir()
    config = parse_args(["--input", str(input_dir)], cwd=tmp_path)

    assert config.host == DEFAULT_HOST
    assert config.port == DEFAULT_PORT
    assert config.calling_ae == DEFAULT_CALLING_AE
    assert config.called_ae == DEFAULT_CALLED_AE
    assert config.study_delay == DEFAULT_STUDY_DELAY
    assert config.connect_timeout == DEFAULT_CONNECT_TIMEOUT
    assert config.dimse_timeout == DEFAULT_DIMSE_TIMEOUT
    assert config.max_pdu == DEFAULT_MAX_PDU
    assert config.log_format == DEFAULT_LOG_FORMAT
    assert config.verbose is False
    assert config.echo is False
    assert config.input == input_dir
    assert config.config_path is None


def test_zero_args_no_config_returns_two(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as exc_info:
        parse_args([], cwd=tmp_path)
    assert "sender-lite.toml" in str(exc_info.value)


def test_zero_args_default_config_resolves(tmp_path: Path) -> None:
    input_dir = tmp_path / "dicom"
    input_dir.mkdir()
    _write_toml(
        tmp_path / "sender-lite.toml",
        f'input = "./dicom"\nhost = "{DEFAULT_HOST}"\n',
    )
    config = parse_args([], cwd=tmp_path)

    assert config.input == input_dir
    assert config.config_path == tmp_path / "sender-lite.toml"
    assert config.host == DEFAULT_HOST


def test_echo_does_not_require_input(tmp_path: Path) -> None:
    config = parse_args(["--echo"], cwd=tmp_path)

    assert config.echo is True
    assert config.input is None


def test_echo_with_default_config_does_not_require_input(tmp_path: Path) -> None:
    _write_toml(tmp_path / "sender-lite.toml", f'host = "{DEFAULT_HOST}"\n')
    config = parse_args(["--echo"], cwd=tmp_path)
    assert config.echo is True
    assert config.input is None
    assert config.config_path == tmp_path / "sender-lite.toml"


def test_cli_overrides_toml(tmp_path: Path) -> None:
    input_dir = tmp_path / "dicom"
    input_dir.mkdir()
    _write_toml(
        tmp_path / "sender-lite.toml",
        'input = "./dicom"\nhost = "10.0.0.1"\nport = 2000\nverbose = true\n',
    )
    config = parse_args(
        ["--host", "192.168.1.1", "--port", "3000"],
        cwd=tmp_path,
    )

    assert config.host == "192.168.1.1"
    assert config.port == 3000
    assert config.verbose is True  # from TOML
    assert config.input == input_dir  # from TOML


def test_no_verbose_overrides_toml_verbose_true(tmp_path: Path) -> None:
    input_dir = tmp_path / "dicom"
    input_dir.mkdir()
    _write_toml(
        tmp_path / "sender-lite.toml",
        'input = "./dicom"\nverbose = true\n',
    )
    config = parse_args(["--no-verbose"], cwd=tmp_path)

    assert config.verbose is False


def test_toml_relative_input_resolved_against_toml_dir(tmp_path: Path) -> None:
    sub = tmp_path / "cfg"
    sub.mkdir()
    dicom = sub / "dicom"
    dicom.mkdir()
    _write_toml(sub / "sender-lite.toml", 'input = "./dicom"\n')
    config = parse_args(["--config", str(sub / "sender-lite.toml")], cwd=tmp_path)

    assert config.input == dicom


def test_cli_relative_input_resolved_against_cwd(tmp_path: Path) -> None:
    input_dir = tmp_path / "dicom"
    input_dir.mkdir()
    config = parse_args(["--input", "dicom"], cwd=tmp_path)

    assert config.input == input_dir


def test_unknown_toml_key_errors(tmp_path: Path) -> None:
    _write_toml(tmp_path / "sender-lite.toml", 'input = "./x"\nunknown_key = 1\n')
    with pytest.raises(ValueError, match="unknown config key"):
        parse_args([], cwd=tmp_path)


def test_wrong_toml_type_errors(tmp_path: Path) -> None:
    _write_toml(tmp_path / "sender-lite.toml", 'port = "not-an-int"\n')
    with pytest.raises(ValueError, match="must be an integer"):
        parse_args([], cwd=tmp_path)


def test_wrong_toml_type_bool_for_int_errors(tmp_path: Path) -> None:
    _write_toml(tmp_path / "sender-lite.toml", "port = true\n")
    with pytest.raises(ValueError, match="must be an integer"):
        parse_args([], cwd=tmp_path)


@pytest.mark.parametrize(
    "argv,expected_error",
    [
        (["--port", "0"], ValueError),
        (["--port", "70000"], ValueError),
        (["--max-pdu", "0"], ValueError),
        (["--calling-ae", "é"], ValueError),
        (["--calling-ae", ""], ValueError),
        (["--format", "xml"], SystemExit),
        (["--study-delay", "-1"], ValueError),
        (["--connect-timeout", "0"], ValueError),
        (["--dimse-timeout", "-0.1"], ValueError),
    ],
)
def test_invalid_cli_values_rejected(
    tmp_path: Path, argv: list[str], expected_error: type[BaseException]
) -> None:
    with pytest.raises(expected_error):
        parse_args(argv, cwd=tmp_path)


def test_missing_input_for_sender_run_errors(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="input is required"):
        parse_args(["--host", "127.0.0.1"], cwd=tmp_path)


def test_help_bypasses_validation() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--help"])
    assert exc_info.value.code == 0


def test_version_bypasses_validation() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0


def test_explicit_config_path_not_found_errors(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="config file not found"):
        parse_args(["--config", str(tmp_path / "missing.toml")], cwd=tmp_path)


def test_toml_input_not_required_for_echo(tmp_path: Path) -> None:
    _write_toml(tmp_path / "sender-lite.toml", f'host = "{DEFAULT_HOST}"\n')
    config = parse_args(["--echo", "--config", str(tmp_path / "sender-lite.toml")], cwd=tmp_path)

    assert config.echo is True
    assert config.input is None


def test_input_symlink_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(ValueError, match="symlink"):
        parse_args(["--input", str(link)], cwd=tmp_path)


def test_input_nonexistent_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        parse_args(["--input", str(tmp_path / "nope")], cwd=tmp_path)


def test_config_dataclass_is_frozen(tmp_path: Path) -> None:
    config = parse_args(["--echo"], cwd=tmp_path)
    with pytest.raises(AttributeError):
        config.port = 9999  # type: ignore[mutation]
