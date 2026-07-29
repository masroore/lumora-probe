"""Portable, self-contained capture directories and ``.lpcap`` archives."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from lumora_probe.core.config import is_uuid7
from lumora_probe.core.errors import LumoraError
from lumora_probe.core.paths import assert_contained, resolve_capture_path

CURRENT_CAPTURE_FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
EVENTS_NAME = "events.jsonl"
PDUS_NAME = "pdus.jsonl"
OBJECTS_DIRECTORY = "objects"


class CaptureFormatError(LumoraError):
    """A capture directory or archive does not satisfy the format contract."""


class CaptureIntegrityError(CaptureFormatError):
    """A content-addressed capture object failed verification."""


class UnsupportedCaptureFormatError(CaptureFormatError):
    """A capture was written by a newer unsupported format version."""


class CaptureFidelity(StrEnum):
    """Evidence layers present in a capture."""

    EVENTS = "events"
    PROTOCOL = "protocol"
    WIRE = "wire"
    OBJECTS = "objects"


class FsyncPolicy(StrEnum):
    """Durability policy for append-only capture records."""

    ALWAYS = "always"
    FLUSH = "flush"
    NEVER = "never"


class CaptureObject(BaseModel):
    """Manifest entry describing one content-addressed DICOM object."""

    model_config = ConfigDict(extra="allow", frozen=True)

    digest: str
    study_uid: str
    series_uid: str
    sop_instance_uid: str
    size: int = Field(ge=0)
    transfer_syntax_uid: str | None = None
    rows: int | None = Field(default=None, gt=0)
    columns: int | None = Field(default=None, gt=0)

    @field_validator("digest")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("digest must be a lowercase SHA-256 hex digest")
        return value


class ClockAnchor(BaseModel):
    """Wall and monotonic samples anchoring a capture's event timeline."""

    model_config = ConfigDict(extra="allow", frozen=True)

    wall_time: datetime
    monotonic_ns: int = Field(ge=0)


class CaptureManifest(BaseModel):
    """Boundary representation of the immutable capture manifest."""

    model_config = ConfigDict(extra="allow", frozen=True)

    format_version: int = Field(default=CURRENT_CAPTURE_FORMAT_VERSION, ge=1)
    capture_id: str
    created_at: datetime
    completed_at: datetime | None = None
    fidelity: CaptureFidelity
    state: str = "completed"
    source: str = "live"
    source_capture_id: str | None = None
    redaction_profile: str | None = None
    partial: bool = False
    promoted_from_buffer: bool = False
    incomplete_aggregates: tuple[str, ...] = ()
    client_asserted_event_count: int = Field(default=0, ge=0)
    clock_anchor: ClockAnchor | None = None
    objects: tuple[CaptureObject, ...] = ()

    @field_validator("capture_id")
    @classmethod
    def validate_capture_id(cls, value: str) -> str:
        if not is_uuid7(value):
            raise ValueError("capture_id must be a UUIDv7")
        return value

    @field_validator("source_capture_id")
    @classmethod
    def validate_source_capture_id(cls, value: str | None) -> str | None:
        if value is not None and not is_uuid7(value):
            raise ValueError("source_capture_id must be a UUIDv7")
        return value

    @field_validator("incomplete_aggregates")
    @classmethod
    def normalize_incomplete_aggregates(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(value)

    def with_objects(self, objects: tuple[CaptureObject, ...]) -> CaptureManifest:
        """Return a sealed manifest containing the final object inventory."""
        return self.model_copy(update={"objects": objects})


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    """Result of verifying a capture's manifest and object digests."""

    valid: bool
    checked: tuple[str, ...]
    missing: tuple[str, ...]
    mismatched: tuple[str, ...]
    unexpected: tuple[str, ...]


class JsonlWriter:
    """Append-only JSONL writer with an explicit flush/fsync policy."""

    def __init__(
        self,
        path: Path,
        *,
        fsync_policy: FsyncPolicy = FsyncPolicy.ALWAYS,
    ) -> None:
        self.path = path
        self.fsync_policy = FsyncPolicy(fsync_policy)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: Mapping[str, Any] | BaseModel) -> None:
        raw = (
            record.model_dump_json(exclude_none=False, by_alias=True).encode("utf-8")
            if isinstance(record, BaseModel)
            else _canonical_json(record).encode("utf-8")
        )
        self.append_raw(raw)

    def append_raw(self, raw: bytes) -> None:
        if not raw or b"\n" in raw.rstrip(b"\n"):
            raise CaptureFormatError(
                code="LUMORA-CAPTURE-FMT-001",
                message="JSONL record must contain exactly one JSON value",
                remediation="Pass one serialized JSON object without embedded newlines.",
                context={"path": str(self.path)},
            )
        try:
            json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CaptureFormatError(
                code="LUMORA-CAPTURE-FMT-002",
                message="JSONL record is not valid UTF-8 JSON",
                remediation="Serialize a valid JSON envelope before appending it.",
                context={"path": str(self.path)},
            ) from exc
        line = raw if raw.endswith(b"\n") else raw + b"\n"
        with self.path.open("ab") as handle:
            handle.write(line)
            if self.fsync_policy is not FsyncPolicy.NEVER:
                handle.flush()
            if self.fsync_policy is FsyncPolicy.ALWAYS:
                os.fsync(handle.fileno())


class ContentAddressedObjectStore:
    """SHA-256 addressed object storage with atomic writes and verification."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, digest: str) -> Path:
        _validate_digest(digest)
        return assert_contained(self.root / digest, self.root)

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        destination = self.path_for(digest)
        if destination.is_file():
            return digest
        temporary = destination.with_name(f".{destination.name}.tmp")
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        return digest

    def put_file(self, source: Path) -> str:
        digest_hash = hashlib.sha256()
        with source.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest_hash.update(chunk)
        digest = digest_hash.hexdigest()
        destination = self.path_for(digest)
        if destination.is_file():
            return digest
        temporary = destination.with_name(f".{destination.name}.tmp")
        with source.open("rb") as source_handle, temporary.open("wb") as destination_handle:
            shutil.copyfileobj(source_handle, destination_handle, length=1024 * 1024)
            destination_handle.flush()
            os.fsync(destination_handle.fileno())
        os.replace(temporary, destination)
        return digest

    def read(self, digest: str) -> bytes:
        return self.path_for(digest).read_bytes()

    def verify(self, digest: str) -> bool:
        path = self.path_for(digest)
        if not path.is_file():
            return False
        return hashlib.sha256(path.read_bytes()).hexdigest() == digest

    def digests(self) -> tuple[str, ...]:
        return tuple(sorted(path.name for path in self.root.iterdir() if path.is_file()))


class CapturePackageWriter:
    """Writer for a working-form capture directory."""

    def __init__(
        self,
        root: Path,
        manifest: CaptureManifest,
        *,
        fsync_policy: FsyncPolicy = FsyncPolicy.ALWAYS,
    ) -> None:
        self.root = root.expanduser().resolve()
        self.capture_path = resolve_capture_path(manifest.capture_id, allowed_root=self.root)
        self.manifest = manifest
        self.fsync_policy = FsyncPolicy(fsync_policy)
        self._objects: dict[str, CaptureObject] = {item.digest: item for item in manifest.objects}
        self._sealed = False
        self.capture_path.mkdir(parents=True, exist_ok=True)
        (self.capture_path / OBJECTS_DIRECTORY).mkdir(exist_ok=True)
        self._write_manifest(manifest)

    @property
    def objects(self) -> ContentAddressedObjectStore:
        return ContentAddressedObjectStore(self.capture_path / OBJECTS_DIRECTORY)

    def append_event(self, event: Mapping[str, Any] | BaseModel) -> None:
        self._ensure_open()
        JsonlWriter(self.capture_path / EVENTS_NAME, fsync_policy=self.fsync_policy).append(event)

    def append_event_raw(self, raw: bytes) -> None:
        self._ensure_open()
        JsonlWriter(self.capture_path / EVENTS_NAME, fsync_policy=self.fsync_policy).append_raw(raw)

    def append_pdu(self, pdu: Mapping[str, Any] | BaseModel) -> None:
        self._ensure_open()
        JsonlWriter(self.capture_path / PDUS_NAME, fsync_policy=self.fsync_policy).append(pdu)

    def append_pdu_raw(self, raw: bytes) -> None:
        self._ensure_open()
        JsonlWriter(self.capture_path / PDUS_NAME, fsync_policy=self.fsync_policy).append_raw(raw)

    def put_object(
        self,
        data: bytes,
        *,
        study_uid: str,
        series_uid: str,
        sop_instance_uid: str,
        transfer_syntax_uid: str | None = None,
        rows: int | None = None,
        columns: int | None = None,
    ) -> CaptureObject:
        self._ensure_open()
        digest = self.objects.put(data)
        item = CaptureObject(
            digest=digest,
            study_uid=study_uid,
            series_uid=series_uid,
            sop_instance_uid=sop_instance_uid,
            size=len(data),
            transfer_syntax_uid=transfer_syntax_uid,
            rows=rows,
            columns=columns,
        )
        self._objects[digest] = item
        return item

    def seal(self, *, completed_at: datetime | None = None) -> CaptureManifest:
        self._ensure_open()
        update: dict[str, Any] = {"objects": tuple(self._objects.values())}
        if completed_at is not None:
            update["completed_at"] = completed_at
        self.manifest = self.manifest.model_copy(update=update)
        self._write_manifest(self.manifest)
        self._sealed = True
        return self.manifest

    def _write_manifest(self, manifest: CaptureManifest) -> None:
        destination = self.capture_path / MANIFEST_NAME
        temporary = destination.with_name(f".{destination.name}.tmp")
        temporary.write_bytes(
            _canonical_json(manifest.model_dump(mode="json")).encode("utf-8") + b"\n"
        )
        if self.fsync_policy is not FsyncPolicy.NEVER:
            with temporary.open("ab") as handle:
                handle.flush()
                if self.fsync_policy is FsyncPolicy.ALWAYS:
                    os.fsync(handle.fileno())
        os.replace(temporary, destination)

    def _ensure_open(self) -> None:
        if self._sealed:
            raise CaptureFormatError(
                code="LUMORA-CAPTURE-FMT-003",
                message="Capture package is sealed",
                remediation="Create a new capture or write records before calling seal().",
                context={"path": str(self.capture_path)},
            )


@dataclass(frozen=True, slots=True)
class CapturePackage:
    """Read-only access to a capture working directory."""

    path: Path

    @classmethod
    def open(cls, path: Path) -> CapturePackage:
        resolved = path.expanduser().resolve()
        if not resolved.is_dir():
            raise CaptureFormatError(
                code="LUMORA-CAPTURE-FMT-004",
                message=f"Capture directory does not exist: {path}",
                remediation="Provide an existing capture directory or unpack a .lpcap archive first.",
                context={"path": str(path)},
            )
        manifest = resolved / MANIFEST_NAME
        if not manifest.is_file():
            raise CaptureFormatError(
                code="LUMORA-CAPTURE-FMT-005",
                message=f"Capture manifest is missing: {manifest}",
                remediation="Restore manifest.json before indexing this capture.",
                context={"path": str(manifest)},
            )
        _read_manifest(manifest)
        return cls(resolved)

    @property
    def manifest(self) -> CaptureManifest:
        return _read_manifest(self.path / MANIFEST_NAME)

    @property
    def objects(self) -> ContentAddressedObjectStore:
        return ContentAddressedObjectStore(self.path / OBJECTS_DIRECTORY)

    def verify(self) -> IntegrityReport:
        expected = {item.digest for item in self.manifest.objects}
        actual = set(self.objects.digests())
        checked = tuple(sorted(expected & actual))
        missing = tuple(sorted(expected - actual))
        unexpected = tuple(sorted(actual - expected))
        mismatched = tuple(digest for digest in checked if not self.objects.verify(digest))
        return IntegrityReport(
            valid=not missing and not mismatched,
            checked=checked,
            missing=missing,
            mismatched=mismatched,
            unexpected=unexpected,
        )

    def verify_or_raise(self) -> IntegrityReport:
        report = self.verify()
        if not report.valid:
            raise CaptureIntegrityError(
                code="LUMORA-CAPTURE-INT-001",
                message="Capture object integrity verification failed",
                remediation="Restore the missing or altered object before using this capture.",
                context={
                    "path": str(self.path),
                    "missing": report.missing,
                    "mismatched": report.mismatched,
                },
            )
        return report

    def pack(self, archive_path: Path) -> Path:
        return pack_capture(self.path, archive_path)


def pack_capture(source: Path, archive_path: Path) -> Path:
    """Pack a working capture directory into a deterministic deflated archive."""
    package = CapturePackage.open(source)
    destination = archive_path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package.path.rglob("*")):
            if path.is_symlink():
                raise CaptureFormatError(
                    code="LUMORA-CAPTURE-FMT-006",
                    message="Symlinks are not allowed in a capture archive",
                    remediation="Replace symlinks with regular files before packing.",
                    context={"path": str(path)},
                )
            if path.is_file():
                archive.write(path, path.relative_to(package.path).as_posix())
    os.replace(temporary, destination)
    return destination


def unpack_capture(archive_path: Path, destination_root: Path) -> Path:
    """Safely unpack a .lpcap archive, rejecting traversal and symlink entries."""
    archive_path = archive_path.expanduser().resolve()
    destination_root = destination_root.expanduser().resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        for member in members:
            target = assert_contained(destination_root / member.filename, destination_root)
            if _zip_member_is_symlink(member):
                raise CaptureFormatError(
                    code="LUMORA-CAPTURE-FMT-007",
                    message="Symlinks are not allowed in a capture archive",
                    remediation="Create the archive from a regular capture directory.",
                    context={"member": member.filename},
                )
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
    return CapturePackage.open(destination_root).path


def _read_manifest(path: Path) -> CaptureManifest:
    try:
        manifest = CaptureManifest.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise CaptureFormatError(
            code="LUMORA-CAPTURE-FMT-008",
            message=f"Capture manifest is invalid: {path}",
            remediation="Regenerate the manifest with a supported Lumora Probe release.",
            context={"path": str(path)},
        ) from exc
    if manifest.format_version > CURRENT_CAPTURE_FORMAT_VERSION:
        raise UnsupportedCaptureFormatError(
            code="LUMORA-CAPTURE-FMT-009",
            message=f"Capture format version {manifest.format_version} is unsupported",
            remediation="Upgrade Lumora Probe before opening this capture.",
            context={"path": str(path), "supported": CURRENT_CAPTURE_FORMAT_VERSION},
        )
    return manifest


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_digest(digest: str) -> None:
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise CaptureFormatError(
            code="LUMORA-CAPTURE-INT-002",
            message="Object digest is not a lowercase SHA-256 value",
            remediation="Use the digest returned by ContentAddressedObjectStore.",
            context={"digest": digest},
        )


def _zip_member_is_symlink(member: zipfile.ZipInfo) -> bool:
    mode = (member.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


__all__ = [
    "CURRENT_CAPTURE_FORMAT_VERSION",
    "CaptureFidelity",
    "CaptureFormatError",
    "CaptureIntegrityError",
    "CaptureManifest",
    "CaptureObject",
    "CapturePackage",
    "CapturePackageWriter",
    "ClockAnchor",
    "ContentAddressedObjectStore",
    "FsyncPolicy",
    "IntegrityReport",
    "JsonlWriter",
    "UnsupportedCaptureFormatError",
    "pack_capture",
    "unpack_capture",
]
