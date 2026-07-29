"""Capture index persistence, discovery, and rebuild operations."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import tempfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from lumora_probe.core.storage import StorageDatabases, rebuild_study_projection

from .format import (
    CaptureFormatError,
    CaptureObject,
    CapturePackage,
    CapturePackageWriter,
    FsyncPolicy,
    unpack_capture,
)


class RepositoryClock(Protocol):
    """Injected wall and monotonic clock used for recovery timestamps."""

    def now(self) -> datetime: ...


@dataclass(frozen=True, slots=True)
class CaptureIndexRecord:
    """Explicit projection row derived from one capture manifest."""

    capture_id: str
    path: str
    source_root: str
    format_version: int
    created_at: datetime
    completed_at: datetime | None
    state: str
    fidelity: str
    partial: bool
    promoted_from_buffer: bool
    interruption_reason: str | None
    manifest_sha256: str
    indexed_at: datetime
    objects: tuple[CaptureObject, ...]


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    """Retention rules applied to sealed captures outside the ring buffer."""

    max_captures: int | None = None
    max_bytes: int | None = None

    def __post_init__(self) -> None:
        if self.max_captures is not None and self.max_captures < 0:
            raise ValueError("max_captures must not be negative")
        if self.max_bytes is not None and self.max_bytes < 0:
            raise ValueError("max_bytes must not be negative")
        if self.max_captures is None and self.max_bytes is None:
            raise ValueError("at least one retention limit is required")

    def select(self, records: Iterable[CaptureIndexRecord]) -> tuple[str, ...]:
        ordered = sorted(records, key=lambda record: (record.created_at, record.capture_id))
        retained = list(reversed(ordered))
        if self.max_captures is not None:
            retained = retained[: self.max_captures]
        if self.max_bytes is not None:
            total = 0
            size_limited: list[CaptureIndexRecord] = []
            for record in retained:
                size = sum(item.size for item in record.objects)
                if total + size > self.max_bytes:
                    continue
                size_limited.append(record)
                total += size
            retained = size_limited
        retained_ids = {record.capture_id for record in retained}
        return tuple(
            record.capture_id for record in ordered if record.capture_id not in retained_ids
        )


def capture_to_row(record: CaptureIndexRecord) -> tuple[object, ...]:
    """Map a projection record to the canonical captures table row."""
    return (
        record.capture_id,
        record.path,
        record.source_root,
        record.format_version,
        record.created_at.isoformat(),
        record.completed_at.isoformat() if record.completed_at else None,
        record.state,
        record.fidelity,
        int(record.partial),
        int(record.promoted_from_buffer),
        record.interruption_reason,
        record.manifest_sha256,
        record.indexed_at.isoformat(),
    )


def row_to_capture(
    row: Iterable[object], objects: tuple[CaptureObject, ...] = ()
) -> CaptureIndexRecord:
    """Map a SQLite row to an explicit projection record."""
    values = tuple(row)
    return CaptureIndexRecord(
        capture_id=str(values[0]),
        path=str(values[1]),
        source_root=str(values[2]),
        format_version=int(values[3]),
        created_at=_parse_datetime(values[4]),
        completed_at=_parse_optional_datetime(values[5]),
        state=str(values[6]),
        fidelity=str(values[7]),
        partial=bool(values[8]),
        promoted_from_buffer=bool(values[9]),
        interruption_reason=str(values[10]) if values[10] is not None else None,
        manifest_sha256=str(values[11]),
        indexed_at=_parse_datetime(values[12]),
        objects=objects,
    )


class CaptureRepository:
    """Repository whose index rows are always derived from capture directories."""

    def __init__(
        self,
        databases: StorageDatabases,
        *,
        clock: RepositoryClock,
    ) -> None:
        self.databases = databases
        self.clock = clock

    async def index(
        self, package: CapturePackage, *, source_root: Path | None = None
    ) -> CaptureIndexRecord:
        package.verify_or_raise()
        record = self._record_from_package(package, source_root=source_root)
        await asyncio.to_thread(self._write_record, record, package)
        return record

    async def list_captures(self) -> tuple[CaptureIndexRecord, ...]:
        def read() -> tuple[CaptureIndexRecord, ...]:
            with self.databases.index.connection(read_only=True) as connection:
                rows = connection.execute(
                    "SELECT capture_id, path, source_root, format_version, created_at, completed_at, "
                    "state, fidelity, partial, promoted_from_buffer, interruption_reason, "
                    "manifest_sha256, indexed_at FROM captures ORDER BY created_at, capture_id"
                ).fetchall()
                capture_paths = {row["capture_id"]: Path(row["path"]) for row in rows}
                objects = connection.execute(
                    "SELECT capture_id, object_digest, study_uid, series_uid, sop_instance_uid, "
                    "object_path, transfer_syntax_uid, rows, columns FROM instances "
                    "ORDER BY capture_id, instance_id"
                ).fetchall()
                by_capture: dict[str, list[CaptureObject]] = {}
                for row in objects:
                    object_path = capture_paths[row["capture_id"]] / row["object_path"]
                    by_capture.setdefault(row["capture_id"], []).append(
                        CaptureObject(
                            digest=row["object_digest"],
                            study_uid=row["study_uid"],
                            series_uid=row["series_uid"],
                            sop_instance_uid=row["sop_instance_uid"],
                            size=object_path.stat().st_size if object_path.is_file() else 0,
                            transfer_syntax_uid=row["transfer_syntax_uid"],
                            rows=row["rows"],
                            columns=row["columns"],
                        )
                    )
                return tuple(
                    row_to_capture(row, tuple(by_capture.get(row["capture_id"], ())))
                    for row in rows
                )

        return await asyncio.to_thread(read)

    async def projection_snapshot(self) -> bytes:
        """Return deterministic JSON for rebuild byte-comparison tests."""

        def read() -> bytes:
            with self.databases.index.connection(read_only=True) as connection:
                tables = {
                    "captures": connection.execute(
                        "SELECT * FROM captures ORDER BY capture_id"
                    ).fetchall(),
                    "studies": connection.execute(
                        "SELECT * FROM studies ORDER BY study_uid"
                    ).fetchall(),
                    "series": connection.execute(
                        "SELECT * FROM series ORDER BY study_uid, series_uid"
                    ).fetchall(),
                    "instances": connection.execute(
                        "SELECT * FROM instances ORDER BY instance_id"
                    ).fetchall(),
                    "event_window": connection.execute(
                        "SELECT * FROM event_window ORDER BY capture_id, sequence"
                    ).fetchall(),
                }
                payload = {table: [dict(row) for row in rows] for table, rows in tables.items()}
                return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

        return await asyncio.to_thread(read)

    async def rebuild(
        self,
        primary_root: Path,
        *,
        additional_roots: Iterable[Path] = (),
    ) -> tuple[CaptureIndexRecord, ...]:
        packages = discover_capture_packages(primary_root, additional_roots=additional_roots)
        await asyncio.to_thread(self.databases.index.initialise)
        records = []
        for package, source_root in packages:
            package = await self.recover_package(package)
            records.append(await self.index(package, source_root=source_root))
        return tuple(records)

    async def recover_package(self, package: CapturePackage) -> CapturePackage:
        """Discard a torn trailing event and mark an active package interrupted."""
        return await asyncio.to_thread(self._recover_package, package)

    async def retention_candidates(self, policy: RetentionPolicy) -> tuple[str, ...]:
        return policy.select(await self.list_captures())

    async def remove_index_entry(self, capture_id: str) -> None:
        await self.databases.index.execute_write(
            "DELETE FROM captures WHERE capture_id = ?", (capture_id,)
        )

    def _record_from_package(
        self, package: CapturePackage, *, source_root: Path | None
    ) -> CaptureIndexRecord:
        manifest = package.manifest
        manifest_path = package.path / "manifest.json"
        return CaptureIndexRecord(
            capture_id=manifest.capture_id,
            path=str(package.path),
            source_root=str((source_root or package.path.parent).expanduser().resolve()),
            format_version=manifest.format_version,
            created_at=manifest.created_at,
            completed_at=manifest.completed_at,
            state=manifest.state,
            fidelity=manifest.fidelity.value,
            partial=manifest.partial,
            promoted_from_buffer=manifest.promoted_from_buffer,
            interruption_reason=manifest.interruption_reason,
            manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            indexed_at=manifest.created_at,
            objects=manifest.objects,
        )

    def _write_record(self, record: CaptureIndexRecord, package: CapturePackage) -> None:
        with self.databases.index.write_transaction() as connection:
            connection.execute("DELETE FROM captures WHERE capture_id = ?", (record.capture_id,))
            connection.execute(
                "INSERT INTO captures(capture_id, path, source_root, format_version, created_at, "
                "completed_at, state, fidelity, partial, promoted_from_buffer, "
                "interruption_reason, manifest_sha256, indexed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                capture_to_row(record),
            )
            connection.executemany(
                "INSERT INTO instances(capture_id, study_uid, series_uid, sop_instance_uid, "
                "object_digest, object_path, transfer_syntax_uid, rows, columns, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (
                        record.capture_id,
                        item.study_uid,
                        item.series_uid,
                        item.sop_instance_uid,
                        item.digest,
                        f"objects/{item.digest}",
                        item.transfer_syntax_uid,
                        item.rows,
                        item.columns,
                        record.created_at.isoformat(),
                    )
                    for item in record.objects
                ),
            )
            rebuild_study_projection(connection)
            for sequence, event in enumerate(
                _read_complete_events(package.path / "events.jsonl"), 1
            ):
                connection.execute(
                    "INSERT INTO event_window(capture_id, sequence, event_id, event_name, "
                    "event_version, observed_at, monotonic_ns, origin, raw_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record.capture_id,
                        sequence,
                        str(event.get("event_id", f"{record.capture_id}:{sequence}")),
                        str(event.get("event_name", "Unknown")),
                        int(event.get("event_version", 1)),
                        str(event.get("observed_at", record.created_at.isoformat())),
                        int(event.get("monotonic_ns", sequence)),
                        str(event.get("origin", "capture")),
                        event["_raw_json"],
                    ),
                )

    def _recover_package(self, package: CapturePackage) -> CapturePackage:
        events_path = package.path / "events.jsonl"
        raw = events_path.read_bytes() if events_path.is_file() else b""
        complete_length, torn = _complete_event_length(raw)
        if torn:
            events_path.write_bytes(raw[:complete_length])

        manifest = package.manifest
        active = manifest.state in {"created", "running", "stopping"}
        if not torn and not active:
            return package
        reason = (
            "torn trailing event record discarded"
            if torn
            else "capture was active during process restart"
        )
        interrupted = manifest.model_copy(
            update={
                "state": "interrupted",
                "completed_at": self.clock.now(),
                "interruption_reason": reason,
            }
        )
        CapturePackageWriter(
            package.path.parent,
            interrupted,
            fsync_policy=FsyncPolicy.ALWAYS,
        )
        return CapturePackage.open(package.path)


def discover_capture_packages(
    primary_root: Path,
    *,
    additional_roots: Iterable[Path] = (),
) -> tuple[tuple[CapturePackage, Path], ...]:
    """Discover directories and materialize dropped archives into the primary root."""
    primary_root = primary_root.expanduser().resolve()
    primary_root.mkdir(parents=True, exist_ok=True)
    discovered: dict[str, tuple[CapturePackage, Path]] = {}
    for root in (primary_root, *(path.expanduser().resolve() for path in additional_roots)):
        if not root.is_dir():
            continue
        for candidate in sorted(root.iterdir(), key=lambda path: path.name):
            if candidate.is_dir() and (candidate / "manifest.json").is_file():
                package = CapturePackage.open(candidate)
                discovered.setdefault(package.manifest.capture_id, (package, root))
            elif candidate.is_file() and candidate.suffix.lower() == ".lpcap":
                package, source_root = _materialize_archive(candidate, primary_root)
                discovered.setdefault(package.manifest.capture_id, (package, source_root))
    return tuple(discovered.values())


def _materialize_archive(archive: Path, primary_root: Path) -> tuple[CapturePackage, Path]:
    with tempfile.TemporaryDirectory(prefix="lumora-lpcap-") as temporary:
        unpacked_path = unpack_capture(archive, Path(temporary))
        unpacked = CapturePackage.open(unpacked_path)
        manifest = unpacked.manifest
        destination = primary_root / manifest.capture_id
        if not destination.exists():
            shutil.copytree(unpacked.path, destination)
        return CapturePackage.open(destination), archive.parent


def _read_complete_events(path: Path) -> Iterator[dict[str, object]]:
    if not path.is_file():
        return
    lines = path.read_bytes().splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.endswith((b"\n", b"\r")):
            if index == len(lines) - 1:
                return
            raise CaptureFormatError(
                code="LUMORA-CAPTURE-FMT-010",
                message=f"Torn event record is not trailing: {path}:{index + 1}",
                remediation="Restore the capture from a sealed copy before rebuilding the index.",
                context={"path": str(path), "line": index + 1},
            )
        raw = line.rstrip(b"\r\n")
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            if index == len(lines) - 1:
                return
            raise CaptureFormatError(
                code="LUMORA-CAPTURE-FMT-011",
                message=f"Invalid event JSON: {path}:{index + 1}",
                remediation="Repair the capture or remove only the torn trailing record.",
                context={"path": str(path), "line": index + 1},
            ) from exc
        if not isinstance(event, dict):
            raise CaptureFormatError(
                code="LUMORA-CAPTURE-FMT-012",
                message=f"Event record is not a JSON object: {path}:{index + 1}",
                remediation="Persist event envelopes as JSON objects.",
                context={"path": str(path), "line": index + 1},
            )
        event["_raw_json"] = raw.decode("utf-8")
        yield event


def _complete_event_length(raw: bytes) -> tuple[int, bool]:
    """Return the durable prefix length and whether the tail was torn."""
    if not raw:
        return 0, False
    offset = 0
    lines = raw.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.endswith((b"\n", b"\r")):
            return offset, True
        candidate = line.rstrip(b"\r\n")
        try:
            json.loads(candidate)
        except json.JSONDecodeError as exc:
            if index == len(lines) - 1:
                return offset, True
            raise CaptureFormatError(
                code="LUMORA-CAPTURE-FMT-014",
                message="Invalid event JSON is not trailing",
                remediation="Restore the capture from a sealed copy before rebuilding the index.",
                context={"line": index + 1},
            ) from exc
        offset += len(line)
    return offset, False


def _parse_datetime(value: object) -> datetime:
    return datetime.fromisoformat(str(value))


def _parse_optional_datetime(value: object) -> datetime | None:
    return None if value is None else _parse_datetime(value)


__all__: tuple[str, ...] = ()
