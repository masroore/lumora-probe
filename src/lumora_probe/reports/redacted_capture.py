# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Create a new capture containing tag-redacted DICOM object copies."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

from pydicom.dataset import Dataset
from pydicom.filereader import dcmread  # pyright: ignore[reportUnknownVariableType]
from pydicom.filewriter import dcmwrite  # pyright: ignore[reportUnknownVariableType]

from lumora_probe.captures.format import (
    CaptureFidelity,
    CaptureFormatError,
    CapturePackage,
    CapturePackageWriter,
)
from lumora_probe.core.paths import resolve_capture_path

from .redaction import DEFAULT_REDACTION_PROFILE, DatasetRedactor, RedactionProfile


class ClockSource(Protocol):
    def now(self) -> datetime: ...


class IdSource(Protocol):
    def new_id(self) -> str: ...


class RedactedCaptureError(CaptureFormatError):
    """A source object could not be safely transformed into a new capture."""


class RedactedCaptureExporter:
    """Write a verified, immutable source capture copy with tag-level redaction."""

    def __init__(
        self,
        *,
        id_generator: IdSource,
        clock: ClockSource,
    ) -> None:
        self.id_generator = id_generator
        self.clock = clock

    def export(
        self,
        source: CapturePackage | Path,
        destination_root: Path,
        *,
        profile_name: str = "default-v1",
        profile: RedactionProfile = DEFAULT_REDACTION_PROFILE,
    ) -> CapturePackage:
        """Create a new object-fidelity capture and preserve the source unchanged."""
        if not profile_name.strip():
            raise ValueError("profile_name must not be empty")
        source_package = (
            source if isinstance(source, CapturePackage) else CapturePackage.open(source)
        )
        if not source_package.manifest.objects:
            raise RedactedCaptureError(
                code="LUMORA-REDACTION-001",
                message="Source capture has no DICOM objects to redact",
                remediation="Use a capture with fidelity=objects and a sealed object inventory.",
                context={"capture_id": source_package.manifest.capture_id},
            )
        source_package.verify_or_raise()

        capture_id = self.id_generator.new_id()
        destination = resolve_capture_path(capture_id, allowed_root=destination_root)
        if destination.exists():
            raise RedactedCaptureError(
                code="LUMORA-REDACTION-002",
                message="Redacted capture destination already exists",
                remediation="Provide a fresh capture identifier.",
                context={"capture_id": capture_id},
            )

        manifest = source_package.manifest.model_copy(
            update={
                "capture_id": capture_id,
                "created_at": self.clock.now(),
                "completed_at": self.clock.now(),
                "fidelity": CaptureFidelity.OBJECTS,
                "source": "redacted",
                "source_capture_id": source_package.manifest.capture_id,
                "redaction_profile": profile_name.strip(),
                "objects": (),
            }
        )
        writer = CapturePackageWriter(destination_root, manifest)
        self._copy_stream(
            source_package.path / "events.jsonl", writer.capture_path / "events.jsonl"
        )
        self._copy_stream(source_package.path / "pdus.jsonl", writer.capture_path / "pdus.jsonl")

        redactor = DatasetRedactor(self.id_generator, profile)
        uid_mapping: dict[str, str] = {}
        warnings: list[dict[str, Any]] = []
        for item in source_package.manifest.objects:
            raw = source_package.objects.read(item.digest)
            try:
                dataset = dcmread(BytesIO(raw), force=True)
                result = redactor.redact(dataset, uid_mapping=uid_mapping)
                output = _serialize(result.dataset)
            except Exception as exc:
                raise RedactedCaptureError(
                    code="LUMORA-REDACTION-003",
                    message="DICOM object could not be safely redacted",
                    remediation="Repair the source object or omit it before retrying.",
                    context={
                        "capture_id": source_package.manifest.capture_id,
                        "digest": item.digest,
                    },
                ) from exc
            warnings.extend(
                {
                    "code": warning.code,
                    "message": warning.message,
                    "tag": str(warning.tag) if warning.tag is not None else None,  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
                }
                for warning in result.warnings
            )
            output_dataset = result.dataset
            writer.put_object(
                output,
                study_uid=_required_uid(output_dataset, "StudyInstanceUID", item.study_uid),
                series_uid=_required_uid(output_dataset, "SeriesInstanceUID", item.series_uid),
                sop_instance_uid=_required_uid(
                    output_dataset, "SOPInstanceUID", item.sop_instance_uid
                ),
                transfer_syntax_uid=_transfer_syntax(output_dataset, item.transfer_syntax_uid),
                rows=_integer_value(output_dataset, "Rows"),
                columns=_integer_value(output_dataset, "Columns"),
            )

        writer.update_manifest(
            manifest.model_copy(
                update={
                    "redaction_warning_count": len(warnings),
                    "redaction_warnings": tuple(warnings),
                    "redaction_uid_mapping_count": len(uid_mapping),
                }
            )
        )
        writer.seal(completed_at=manifest.completed_at)
        return CapturePackage.open(writer.capture_path)

    @staticmethod
    def _copy_stream(source: Path, destination: Path) -> None:
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())


def redact_capture(
    source: CapturePackage | Path,
    destination_root: Path,
    *,
    id_generator: IdSource,
    clock: ClockSource,
    profile_name: str = "default-v1",
    profile: RedactionProfile = DEFAULT_REDACTION_PROFILE,
) -> CapturePackage:
    """Redact a capture into a new package without mutating the source."""
    return RedactedCaptureExporter(id_generator=id_generator, clock=clock).export(
        source,
        destination_root,
        profile_name=profile_name,
        profile=profile,
    )


def _serialize(dataset: Dataset) -> bytes:
    buffer = BytesIO()
    dcmwrite(buffer, dataset, enforce_file_format=True)
    return buffer.getvalue()


def _required_uid(dataset: Dataset, keyword: str, fallback: str) -> str:
    value = getattr(dataset, keyword, fallback)
    return str(value)


def _transfer_syntax(dataset: Dataset, fallback: str | None) -> str | None:
    file_meta = getattr(dataset, "file_meta", None)
    value = getattr(file_meta, "TransferSyntaxUID", None)
    return str(value) if value else fallback


def _integer_value(dataset: Dataset, keyword: str) -> int | None:
    value = getattr(dataset, keyword, None)
    return int(value) if isinstance(value, int) and value > 0 else None


__all__ = [
    "RedactedCaptureError",
    "RedactedCaptureExporter",
    "redact_capture",
]
