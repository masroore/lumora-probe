# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Safe handover export for captures.

The default export drops object data and writes an ``events``-fidelity capture. A
pixel-bearing export is a deliberate opt-in and is labelled as such in its manifest.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Final, Protocol

from lumora_probe.captures.format import (
    EVENTS_NAME,
    OBJECTS_DIRECTORY,
    PDUS_NAME,
    CaptureFidelity,
    CaptureFormatError,
    CaptureIntegrityError,
    CaptureManifest,
    CapturePackage,
    CapturePackageWriter,
)
from lumora_probe.core.paths import assert_contained, resolve_capture_path


class ClockSource(Protocol):
    def now(self) -> datetime: ...


class IdSource(Protocol):
    def new_id(self) -> str: ...


DEFAULT_HANDOVER_PROFILE: Final = "handover-events-v1"
PIXEL_HANDOVER_PROFILE: Final = "handover-pixels-explicit-v1"

# Only manifest metadata useful for understanding the evidence is carried forward.
# In particular, arbitrary source manifest extras and the object inventory are dropped.
HANDOVER_METADATA_FIELDS: Final[tuple[str, ...]] = (
    "partial",
    "promoted_from_buffer",
    "incomplete_aggregates",
    "interruption_reason",
    "client_asserted_event_count",
    "clock_anchor",
    "promotion_requested_start",
    "promotion_requested_end",
    "promotion_actual_start",
    "promotion_actual_end",
    "source_aggregate_ids",
)


class HandoverExporter:
    """Export an immutable capture without modifying its source package.

    ``pixel_bearing=True`` is intentionally required for an export that copies DICOM
    object bytes. The default is object-dropping ``fidelity=events``.
    """

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
        profile: str | None = None,
        pixel_bearing: bool = False,
    ) -> CapturePackage:
        """Create a deterministic handover package under ``destination_root``.

        Events and protocol traces are copied verbatim. The default package contains
        no object bytes. Setting ``pixel_bearing=True`` is the deliberate, explicitly
        labelled opt-in for copying object data; it does not redact or de-identify it.
        """
        source_package = (
            source if isinstance(source, CapturePackage) else CapturePackage.open(source)
        )
        source_manifest = source_package.manifest
        export_id = self.id_generator.new_id()
        if export_id == source_manifest.capture_id:
            raise CaptureFormatError(
                code="LUMORA-CAPTURE-HANDOVER-001",
                message="Handover export identity would overwrite its source capture",
                remediation="Provide a fresh capture identifier from the injected ID generator.",
                context={"capture_id": export_id},
            )

        destination = resolve_capture_path(export_id, allowed_root=destination_root)
        if destination.exists():
            raise CaptureFormatError(
                code="LUMORA-CAPTURE-HANDOVER-002",
                message=f"Handover destination already exists: {destination}",
                remediation="Export to a new destination or provide a fresh capture identifier.",
                context={"path": str(destination)},
            )

        exported_at = self.clock.now()
        selected_profile = profile or (
            PIXEL_HANDOVER_PROFILE if pixel_bearing else DEFAULT_HANDOVER_PROFILE
        )
        if not selected_profile.strip():
            raise ValueError("handover profile must not be empty")

        manifest = self._manifest(
            source_manifest,
            capture_id=export_id,
            exported_at=exported_at,
            profile=selected_profile,
            pixel_bearing=pixel_bearing,
        )
        writer = CapturePackageWriter(destination_root, manifest)
        self._copy_record(source_package, writer, EVENTS_NAME, destination_root)
        self._copy_record(source_package, writer, PDUS_NAME, destination_root)
        if pixel_bearing:
            self._copy_objects(source_package, writer)

        writer.seal(completed_at=exported_at)
        return CapturePackage.open(writer.capture_path)

    @staticmethod
    def _manifest(
        source: CaptureManifest,
        *,
        capture_id: str,
        exported_at: datetime,
        profile: str,
        pixel_bearing: bool,
    ) -> CaptureManifest:
        values = {field: getattr(source, field) for field in HANDOVER_METADATA_FIELDS}
        manifest = CaptureManifest(
            capture_id=capture_id,
            created_at=exported_at,
            completed_at=exported_at,
            fidelity=CaptureFidelity.OBJECTS if pixel_bearing else CaptureFidelity.EVENTS,
            state="completed",
            source="handover",
            source_capture_id=source.capture_id,
            redaction_profile=profile,
            objects=source.objects if pixel_bearing else (),
            **values,
        )
        return manifest.model_copy(
            update={
                "handover_profile": profile,
                "handover_source_fidelity": source.fidelity.value,
                "handover_pixel_data_included": pixel_bearing,
                "handover_pixel_export_deliberate": pixel_bearing,
                "handover_metadata_fields": HANDOVER_METADATA_FIELDS,
            }
        )

    @staticmethod
    def _copy_record(
        source: CapturePackage,
        writer: CapturePackageWriter,
        name: str,
        destination_root: Path,
    ) -> None:
        source_path = assert_contained(source.path / name, source.path)
        if not source_path.is_file():
            return
        destination = assert_contained(writer.capture_path / name, destination_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination)

    @staticmethod
    def _copy_objects(source: CapturePackage, writer: CapturePackageWriter) -> None:
        """Copy object bytes only for the deliberate pixel-bearing export."""
        for item in source.manifest.objects:
            source_path = assert_contained(
                source.path / OBJECTS_DIRECTORY / item.digest,
                source.path,
            )
            if not source_path.is_file():
                raise CaptureIntegrityError(
                    code="LUMORA-CAPTURE-HANDOVER-003",
                    message=f"Source object is missing: {item.digest}",
                    remediation="Restore the source object before requesting a pixel-bearing export.",
                    context={"capture_id": source.manifest.capture_id, "digest": item.digest},
                )
            if hashlib.sha256(source_path.read_bytes()).hexdigest() != item.digest:
                raise CaptureIntegrityError(
                    code="LUMORA-CAPTURE-HANDOVER-004",
                    message=f"Source object digest does not match its manifest: {item.digest}",
                    remediation="Restore the altered source object before requesting a pixel-bearing export.",
                    context={"capture_id": source.manifest.capture_id, "digest": item.digest},
                )
            writer.objects.put_file(source_path)


def export_handover(
    source: CapturePackage | Path,
    destination_root: Path,
    *,
    id_generator: IdSource,
    clock: ClockSource,
    profile: str | None = None,
    pixel_bearing: bool = False,
) -> CapturePackage:
    """Convenience wrapper for the safe, object-dropping handover export.

    Pixel-bearing output requires ``pixel_bearing=True``. That opt-in is deliberate and
    the resulting manifest records it; no anonymization or de-identification is claimed.
    """
    return HandoverExporter(id_generator=id_generator, clock=clock).export(
        source,
        destination_root,
        profile=profile,
        pixel_bearing=pixel_bearing,
    )
