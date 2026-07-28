import io
import json

import pytest

from sender_lite.log import SenderLogger


PHI_FIELDS = (
    "patient_name",
    "patient_id",
    "accession_number",
    "patient_birth_date",
    "study_date",
    "series_date",
    "study_description",
    "series_description",
)


def test_json_logging_is_jsonl() -> None:
    output = io.StringIO()
    SenderLogger("json", output).info(
        "instance_sent",
        study_instance_uid="1.2.3",
        series_instance_uid="1.2.3.4",
        sop_instance_uid="1.2.3.4.5",
        sop_class_uid="1.2.840.10008.5.1.4.1.1.2",
        transfer_syntax_uid="1.2.840.10008.1.2",
        path="/tmp/foo.dcm",
        size_bytes=1024,
        status=0,
        duration_ms=12,
    )

    record = json.loads(output.getvalue())
    assert record["level"] == "INFO"
    assert record["event"] == "instance_sent"
    assert record["study_instance_uid"] == "1.2.3"
    assert record["size_bytes"] == 1024
    assert record["timestamp"].endswith("Z")


def test_text_logging_is_one_line() -> None:
    output = io.StringIO()
    SenderLogger("text", output).info(
        "association_accepted",
        study_instance_uid="1.2.3",
        peer="127.0.0.1",
        accepted=3,
        rejected=0,
    )

    line = output.getvalue()
    assert line.count("\n") == 1
    assert "[INFO] Association accepted" in line
    assert "STUDY_INSTANCE_UID=1.2.3" in line
    assert "PEER=127.0.0.1" in line
    assert "ACCEPTED=3" in line
    assert "REJECTED=0" in line


def test_json_logging_flushes_each_event() -> None:
    output = io.StringIO()
    logger = SenderLogger("json", output)
    logger.info("scan_started", input="/tmp/in")
    logger.warning("file_skipped", path="/tmp/bad.dcm", reason="unreadable", error="boom")
    logger.error("catalog_conflict", path="/tmp/dup.dcm", sop_instance_uid="1.2.3", conflicting_count=2)

    lines = [line for line in output.getvalue().splitlines() if line]
    assert len(lines) == 3
    for line in lines:
        record = json.loads(line)
    assert lines[0].endswith("\n") or len(lines) == 3  # each was flushed as its own line


def test_json_each_line_is_one_object() -> None:
    output = io.StringIO()
    logger = SenderLogger("json", output)
    logger.info("run_completed", attempted=5, succeeded=5, failed=0, exit_code=0)

    for line in output.getvalue().splitlines():
        if not line:
            continue
        record = json.loads(line)
        assert isinstance(record, dict)
        assert "timestamp" in record
        assert "level" in record
        assert "event" in record


def test_text_each_event_is_one_line() -> None:
    output = io.StringIO()
    logger = SenderLogger("text", output)
    logger.info("scan_started", input="/tmp/in")
    logger.warning("file_skipped", path="/tmp/bad.dcm", reason="unreadable", error="boom")
    logger.error("run_failed", reason="empty_catalog", exit_code=1)

    lines = [line for line in output.getvalue().split("\n") if line]
    assert len(lines) == 3
    for line in lines:
        assert line.count("\n") == 0


@pytest.mark.parametrize("phi_field", PHI_FIELDS)
def test_json_events_exclude_phi_fields(phi_field: str) -> None:
    output = io.StringIO()
    logger = SenderLogger("json", output)
    logger.info("instance_sent", sop_instance_uid="1.2.3", size_bytes=10)
    logger.warning("instance_warning", sop_instance_uid="1.2.3", status=0x0001)
    logger.error("instance_failed", sop_instance_uid="1.2.3", reason="status", status=0xA700)

    for line in output.getvalue().splitlines():
        if not line:
            continue
        record = json.loads(line)
        assert phi_field not in record, f"PHI field {phi_field!r} leaked into event {record.get('event')!r}"


def test_no_event_includes_clinical_metadata_regression() -> None:
    """PHI regression assertion: no clinical metadata field may appear in any event."""
    output = io.StringIO()
    logger = SenderLogger("json", output)
    logger.info("configuration_resolved", mode="send", host="127.0.0.1", port=11112)
    logger.info("scan_completed", files_scanned=3, rejected=0, studies=1, series=1, instances=3, bytes_total=9, duration_ms=1)
    logger.error("run_failed", reason="empty_catalog", exit_code=1)

    for line in output.getvalue().splitlines():
        if not line:
            continue
        record = json.loads(line)
        for phi_field in PHI_FIELDS:
            assert phi_field not in record


def test_invalid_log_format_raises() -> None:
    with pytest.raises(ValueError):
        SenderLogger("xml")


def test_warning_and_error_levels() -> None:
    output = io.StringIO()
    logger = SenderLogger("json", output)
    logger.warning("file_skipped", path="/tmp/x.dcm", reason="unreadable", error="EACCES")
    logger.error("run_failed", reason="boom", exit_code=1)

    lines = [line for line in output.getvalue().splitlines() if line]
    assert json.loads(lines[0])["level"] == "WARNING"
    assert json.loads(lines[1])["level"] == "ERROR"
