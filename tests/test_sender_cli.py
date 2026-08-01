# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Tests for sender_lite.cli orchestration."""

from __future__ import annotations

import signal
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sender_lite.catalog import (
    Catalog,
    CatalogError,
    CatalogInstance,
    CatalogIssue,
    SeriesCatalog,
    StudyBatch,
)
from sender_lite.cli import main
from sender_lite.sender import EchoResult, InstanceResult, StudyResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


STUDY_UID_1 = "1.2.3.4.5.100"
STUDY_UID_2 = "1.2.3.4.5.200"
SERIES_UID = "1.2.3.4.5.100.1"
SOP_CLASS = "1.2.840.10008.5.1.4.1.1.2"
TS_EXPLICIT = "1.2.840.10008.1.2.1"


def _make_instance(
    path: Path,
    sop_instance_uid: str = "1.2.3.4.5.6.7.8",
) -> CatalogInstance:
    return CatalogInstance(
        path=path,
        size_bytes=100,
        study_uid=STUDY_UID_1,
        series_uid=SERIES_UID,
        sop_instance_uid=sop_instance_uid,
        sop_class_uid=SOP_CLASS,
        transfer_syntax_uid=TS_EXPLICIT,
        instance_number=1,
    )


def _make_study(study_uid: str, instances: list[CatalogInstance]) -> StudyBatch:
    series = SeriesCatalog(series_uid=SERIES_UID, instances=tuple(instances))
    return StudyBatch(study_uid=study_uid, series=(series,))


def _make_catalog(
    studies: tuple[StudyBatch, ...] = (),
    issues: tuple[CatalogIssue, ...] = (),
    scanned_count: int = 0,
    rejected_count: int = 0,
) -> Catalog:
    sendable = sum(s.instance_count for s in studies)
    series_count = sum(len(s.series) for s in studies)
    total_bytes = sum(s.total_bytes for s in studies)
    return Catalog(
        studies=studies,
        issues=issues,
        scanned_count=scanned_count,
        rejected_count=rejected_count,
        sendable_count=sendable,
        series_count=series_count,
        study_count=len(studies),
        total_bytes=total_bytes,
    )


def _echo_result(success: bool = True, status: int | None = 0x0000) -> EchoResult:
    return EchoResult(
        success=success,
        status=status,
        duration=0.1,
        error=None if success else "echo failed",
    )


def _instance_result(
    status: str = "success",
    sop_instance_uid: str = "1.2.3.4.5.6.7.8",
) -> InstanceResult:
    return InstanceResult(
        sop_instance_uid=sop_instance_uid,
        sop_class_uid=SOP_CLASS,
        transfer_syntax_uid=TS_EXPLICIT,
        path=Path("/fake/dicom.dcm"),
        size_bytes=100,
        status=status,
        status_code=0x0000 if status == "success" else None,
        reason=None,
        duration=0.05,
    )


def _study_result(
    study_uid: str = STUDY_UID_1,
    succeeded: int = 1,
    warned: int = 0,
    failed: int = 0,
    cancelled: int = 0,
) -> StudyResult:
    attempted = succeeded + warned + failed + cancelled
    instances = tuple(
        _instance_result(status="success", sop_instance_uid=f"1.2.3.{i}") for i in range(succeeded)
    )
    return StudyResult(
        study_uid=study_uid,
        attempted=attempted,
        succeeded=succeeded,
        warned=warned,
        failed=failed,
        cancelled=cancelled,
        duration=0.2,
        instances=instances,
        error=None,
    )


# ---------------------------------------------------------------------------
# Config error
# ---------------------------------------------------------------------------


def test_config_error_returns_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    exit_code = main([])
    assert exit_code == 2


# ---------------------------------------------------------------------------
# Echo mode
# ---------------------------------------------------------------------------


def test_echo_success_returns_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    fake_sender = MagicMock()
    fake_sender.echo.return_value = _echo_result(success=True)

    with patch("sender_lite.cli.Sender", return_value=fake_sender):
        exit_code = main(["--echo"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "echo_completed" in output or "Echo completed" in output
    # §14.2: run_completed is the universal terminal summary, emitted after echo too.
    assert "run_completed" in output or "Run completed" in output


def test_echo_failure_returns_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    fake_sender = MagicMock()
    fake_sender.echo.return_value = _echo_result(success=False, status=None)

    with patch("sender_lite.cli.Sender", return_value=fake_sender):
        exit_code = main(["--echo"])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "echo_completed" in output or "Echo completed" in output
    assert "run_completed" in output or "Run completed" in output


# ---------------------------------------------------------------------------
# Empty catalog
# ---------------------------------------------------------------------------


def test_empty_catalog_returns_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    empty_catalog = _make_catalog()

    with (
        patch("sender_lite.cli.build_catalog", return_value=empty_catalog),
        patch("sender_lite.cli.Sender"),
    ):
        exit_code = main(["--input", str(input_dir)])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "run_failed" in output or "Run failed" in output


# ---------------------------------------------------------------------------
# Catalog build error
# ---------------------------------------------------------------------------


def test_catalog_error_returns_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    with (
        patch("sender_lite.cli.build_catalog", side_effect=CatalogError("bad input")),
        patch("sender_lite.cli.Sender"),
    ):
        exit_code = main(["--input", str(input_dir)])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "run_failed" in output or "Run failed" in output


# ---------------------------------------------------------------------------
# Study loop
# ---------------------------------------------------------------------------


def test_one_study_success_returns_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    inst = _make_instance(input_dir / "test.dcm")
    study = _make_study(STUDY_UID_1, [inst])
    catalog = _make_catalog(studies=(study,), scanned_count=1)

    fake_sender = MagicMock()
    fake_sender.send_study.return_value = _study_result(succeeded=1)

    with (
        patch("sender_lite.cli.build_catalog", return_value=catalog),
        patch("sender_lite.cli.Sender", return_value=fake_sender),
    ):
        exit_code = main(["--input", str(input_dir)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "run_completed" in output or "Run completed" in output


def test_partial_failure_returns_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    inst = _make_instance(input_dir / "test.dcm")
    study = _make_study(STUDY_UID_1, [inst])
    catalog = _make_catalog(studies=(study,), scanned_count=1)

    fake_sender = MagicMock()
    fake_sender.send_study.return_value = _study_result(succeeded=0, failed=1)

    with (
        patch("sender_lite.cli.build_catalog", return_value=catalog),
        patch("sender_lite.cli.Sender", return_value=fake_sender),
    ):
        exit_code = main(["--input", str(input_dir)])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "run_completed" in output or "Run completed" in output


def test_warning_only_returns_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    inst = _make_instance(input_dir / "test.dcm")
    study = _make_study(STUDY_UID_1, [inst])
    catalog = _make_catalog(studies=(study,), scanned_count=1)

    fake_sender = MagicMock()
    fake_sender.send_study.return_value = _study_result(succeeded=0, warned=1)

    with (
        patch("sender_lite.cli.build_catalog", return_value=catalog),
        patch("sender_lite.cli.Sender", return_value=fake_sender),
    ):
        exit_code = main(["--input", str(input_dir)])

    assert exit_code == 0


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def test_cancellation_returns_130(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    inst = _make_instance(input_dir / "test.dcm")
    study = _make_study(STUDY_UID_1, [inst])
    catalog = _make_catalog(studies=(study,), scanned_count=1)

    def set_cancel_on_send(
        study_arg: StudyBatch, cancel_event: threading.Event, **kwargs: object
    ) -> StudyResult:
        cancel_event.set()
        return _study_result(cancelled=1)

    fake_sender = MagicMock()
    fake_sender.send_study.side_effect = set_cancel_on_send

    with (
        patch("sender_lite.cli.build_catalog", return_value=catalog),
        patch("sender_lite.cli.Sender", return_value=fake_sender),
    ):
        exit_code = main(["--input", str(input_dir), "--study-delay", "0"])

    assert exit_code == 130


# ---------------------------------------------------------------------------
# Inter-study delay
# ---------------------------------------------------------------------------


def test_multiple_studies_n_minus_1_delays(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    inst1 = _make_instance(input_dir / "test1.dcm", sop_instance_uid="1.2.3.4.5.6.7.1")
    inst2 = _make_instance(input_dir / "test2.dcm", sop_instance_uid="1.2.3.4.5.6.7.2")
    study1 = _make_study(STUDY_UID_1, [inst1])
    study2 = _make_study(STUDY_UID_2, [inst2])
    catalog = _make_catalog(studies=(study1, study2), scanned_count=2)

    fake_sender = MagicMock()
    fake_sender.send_study.side_effect = [
        _study_result(study_uid=STUDY_UID_1, succeeded=1),
        _study_result(study_uid=STUDY_UID_2, succeeded=1),
    ]

    wait_calls = []
    original_wait = threading.Event.wait

    def track_wait(self: threading.Event, timeout: float | None = None) -> bool:
        wait_calls.append(timeout)
        return original_wait(self, timeout=timeout)

    with (
        patch("sender_lite.cli.build_catalog", return_value=catalog),
        patch("sender_lite.cli.Sender", return_value=fake_sender),
        patch.object(threading.Event, "wait", track_wait),
    ):
        exit_code = main(["--input", str(input_dir), "--study-delay", "0.01"])

    assert exit_code == 0
    assert len(wait_calls) == 1
    assert wait_calls[0] == 0.01


def test_failure_proceeds_to_next_study_after_delay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    inst1 = _make_instance(input_dir / "test1.dcm", sop_instance_uid="1.2.3.4.5.6.7.1")
    inst2 = _make_instance(input_dir / "test2.dcm", sop_instance_uid="1.2.3.4.5.6.7.2")
    study1 = _make_study(STUDY_UID_1, [inst1])
    study2 = _make_study(STUDY_UID_2, [inst2])
    catalog = _make_catalog(studies=(study1, study2), scanned_count=2)

    fake_sender = MagicMock()
    fake_sender.send_study.side_effect = [
        _study_result(study_uid=STUDY_UID_1, failed=1),
        _study_result(study_uid=STUDY_UID_2, succeeded=1),
    ]

    with (
        patch("sender_lite.cli.build_catalog", return_value=catalog),
        patch("sender_lite.cli.Sender", return_value=fake_sender),
    ):
        exit_code = main(["--input", str(input_dir), "--study-delay", "0"])

    assert exit_code == 1
    assert fake_sender.send_study.call_count == 2


# ---------------------------------------------------------------------------
# Signal handler restoration
# ---------------------------------------------------------------------------


def test_handler_restoration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    inst = _make_instance(input_dir / "test.dcm")
    study = _make_study(STUDY_UID_1, [inst])
    catalog = _make_catalog(studies=(study,), scanned_count=1)

    original_sigint = signal.getsignal(signal.SIGINT)

    fake_sender = MagicMock()
    fake_sender.send_study.return_value = _study_result(succeeded=1)

    with (
        patch("sender_lite.cli.build_catalog", return_value=catalog),
        patch("sender_lite.cli.Sender", return_value=fake_sender),
    ):
        main(["--input", str(input_dir)])

    restored_sigint = signal.getsignal(signal.SIGINT)
    assert restored_sigint == original_sigint


# ---------------------------------------------------------------------------
# Log formats
# ---------------------------------------------------------------------------


def test_text_log_mode_produces_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    fake_sender = MagicMock()
    fake_sender.echo.return_value = _echo_result(success=True)

    with patch("sender_lite.cli.Sender", return_value=fake_sender):
        exit_code = main(["--echo", "--format", "text"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Configuration resolved" in output or "configuration_resolved" in output


def test_json_log_mode_produces_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    fake_sender = MagicMock()
    fake_sender.echo.return_value = _echo_result(success=True)

    with patch("sender_lite.cli.Sender", return_value=fake_sender):
        exit_code = main(["--echo", "--format", "json"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"event":"configuration_resolved"' in output


# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------


def test_final_summary_after_partial_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    inst = _make_instance(input_dir / "test.dcm")
    study = _make_study(STUDY_UID_1, [inst])
    catalog = _make_catalog(studies=(study,), scanned_count=1)

    fake_sender = MagicMock()
    fake_sender.send_study.return_value = _study_result(succeeded=0, failed=1)

    with (
        patch("sender_lite.cli.build_catalog", return_value=catalog),
        patch("sender_lite.cli.Sender", return_value=fake_sender),
    ):
        exit_code = main(["--input", str(input_dir)])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "run_completed" in output or "Run completed" in output
    assert "failed=1" in output or "FAILED=1" in output
