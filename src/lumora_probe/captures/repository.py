# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

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
        format_version=int(values[3]),  # pyright: ignore[reportArgumentType]
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
        self.rebuild_errors: tuple[str, ...] = ()

    async def index(
        self,
        package: CapturePackage,
        *,
        source_root: Path | None = None,
        rebuild_projection: bool = True,
    ) -> CaptureIndexRecord:
        package.verify_or_raise()
        record = self._record_from_package(package, source_root=source_root)
        await asyncio.to_thread(self._write_record, record, package, rebuild_projection)
        return record

    async def list_captures(self) -> tuple[CaptureIndexRecord, ...]:
        def read() -> tuple[CaptureIndexRecord, ...]:
            with self.databases.index.connection(read_only=True) as connection:
                rows = connection.execute(
                    "SELECT capture_id, path, source_root, format_version, created_at, completed_at, "
                    "state, fidelity, partial, promoted_from_buffer, interruption_reason, "
                    "manifest_sha256, indexed_at FROM captures ORDER BY created_at, capture_id"
                ).fetchall()
                objects = connection.execute(
                    "SELECT capture_id, object_digest, study_uid, series_uid, sop_instance_uid, "
                    "object_path, transfer_syntax_uid, rows, columns, object_size FROM instances "
                    "ORDER BY capture_id, instance_id"
                ).fetchall()
                by_capture: dict[str, list[CaptureObject]] = {}
                for row in objects:
                    by_capture.setdefault(row["capture_id"], []).append(
                        CaptureObject(
                            digest=row["object_digest"],
                            study_uid=row["study_uid"],
                            series_uid=row["series_uid"],
                            sop_instance_uid=row["sop_instance_uid"],
                            size=int(row["object_size"]),
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

    async def list_captures_page(
        self,
        *,
        offset: int,
        limit: int,
        sort: str | None = None,
        filter: str | None = None,
    ) -> tuple[tuple[CaptureIndexRecord, ...], int]:
        """Read one stable capture page and its count without scanning object files."""
        if offset < 0 or limit < 1:
            raise ValueError("offset must be non-negative and limit must be positive")

        def read() -> tuple[tuple[CaptureIndexRecord, ...], int]:
            with self.databases.index.connection(read_only=True) as connection:
                allowed_sort = {
                    "capture_id": "capture_id",
                    "created_at": "created_at",
                    "completed_at": "completed_at",
                    "state": "state",
                    "fidelity": "fidelity",
                }
                allowed_filter = {
                    "capture_id": "capture_id",
                    "state": "state",
                    "fidelity": "fidelity",
                    "source_root": "source_root",
                }
                clauses: list[str] = []
                parameters: list[object] = []
                if filter:
                    field, separator, expected = filter.partition(":")
                    if separator:
                        column = allowed_filter.get(field)
                        if column is None:
                            raise ValueError(f"unsupported capture filter: {field}")
                        clauses.append(f"LOWER({column}) = LOWER(?)")
                        parameters.append(expected)
                    else:
                        columns = tuple(dict.fromkeys(allowed_filter.values()))
                        clauses.append(
                            " OR ".join(f"LOWER({column}) LIKE LOWER(?)" for column in columns)
                        )
                        parameters.extend([f"%{filter}%"] * len(columns))
                where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
                total = int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM captures{where}", parameters
                    ).fetchone()[0]
                )
                order: list[str] = []
                for raw in (sort or "created_at,capture_id").split(","):
                    descending = raw.startswith("-")
                    name = raw.lstrip("+-")
                    column = allowed_sort.get(name)
                    if column is None:
                        raise ValueError(f"unsupported capture sort: {name}")
                    order.append(f"{column} {'DESC' if descending else 'ASC'}")
                if "capture_id" not in {
                    raw.lstrip("+-") for raw in (sort or "created_at,capture_id").split(",")
                }:
                    order.append("capture_id ASC")
                rows = connection.execute(
                    "SELECT capture_id, path, source_root, format_version, created_at, completed_at, "
                    "state, fidelity, partial, promoted_from_buffer, interruption_reason, "
                    "manifest_sha256, indexed_at FROM captures"
                    f"{where} ORDER BY {', '.join(order)} LIMIT ? OFFSET ?",
                    (*parameters, limit, offset),
                ).fetchall()
                if not rows:
                    return (), total
                capture_ids = tuple(row["capture_id"] for row in rows)
                placeholders = ",".join("?" for _ in capture_ids)
                objects = connection.execute(
                    "SELECT capture_id, object_digest, study_uid, series_uid, sop_instance_uid, "
                    "object_path, transfer_syntax_uid, rows, columns, object_size FROM instances "
                    f"WHERE capture_id IN ({placeholders}) ORDER BY capture_id, instance_id",
                    capture_ids,
                ).fetchall()
                by_capture: dict[str, list[CaptureObject]] = {}
                for row in objects:
                    by_capture.setdefault(row["capture_id"], []).append(
                        CaptureObject(
                            digest=row["object_digest"],
                            study_uid=row["study_uid"],
                            series_uid=row["series_uid"],
                            sop_instance_uid=row["sop_instance_uid"],
                            size=int(row["object_size"]),
                            transfer_syntax_uid=row["transfer_syntax_uid"],
                            rows=row["rows"],
                            columns=row["columns"],
                        )
                    )
                return (
                    tuple(
                        row_to_capture(row, tuple(by_capture.get(row["capture_id"], ())))
                        for row in rows
                    ),
                    total,
                )

        return await asyncio.to_thread(read)

    async def get_capture(self, capture_id: str) -> CaptureIndexRecord | None:
        """Read one indexed capture and its owned objects without materializing the index."""

        def read() -> CaptureIndexRecord | None:
            with self.databases.index.connection(read_only=True) as connection:
                row = connection.execute(
                    "SELECT capture_id, path, source_root, format_version, created_at, completed_at, "
                    "state, fidelity, partial, promoted_from_buffer, interruption_reason, "
                    "manifest_sha256, indexed_at FROM captures WHERE capture_id = ? LIMIT 1",
                    (capture_id,),
                ).fetchone()
                if row is None:
                    return None
                objects = connection.execute(
                    "SELECT object_digest, study_uid, series_uid, sop_instance_uid, object_size, "
                    "transfer_syntax_uid, rows, columns FROM instances WHERE capture_id = ? ORDER BY instance_id",
                    (capture_id,),
                ).fetchall()
                mapped = tuple(
                    CaptureObject(
                        digest=item["object_digest"],
                        study_uid=item["study_uid"],
                        series_uid=item["series_uid"],
                        sop_instance_uid=item["sop_instance_uid"],
                        size=int(item["object_size"]),
                        transfer_syntax_uid=item["transfer_syntax_uid"],
                        rows=item["rows"],
                        columns=item["columns"],
                    )
                    for item in objects
                )
                return row_to_capture(row, mapped)

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
        errors: list[str] = []
        packages = discover_capture_packages(
            primary_root, additional_roots=additional_roots, errors=errors
        )
        self.rebuild_errors = tuple(errors)
        await asyncio.to_thread(self.databases.index.initialise, recreate=True)
        records = []
        for package, source_root in packages:
            try:
                package = await self.recover_package(package)
                records.append(  # pyright: ignore[reportUnknownMemberType]
                    await self.index(package, source_root=source_root, rebuild_projection=False)
                )
            except (CaptureFormatError, OSError, ValueError) as exc:
                self.rebuild_errors = (
                    *self.rebuild_errors,
                    f"{package.path}: {type(exc).__name__}: {exc}",
                )
        await asyncio.to_thread(self._rebuild_projection)
        return tuple(records)  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]

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

    def _write_record(
        self, record: CaptureIndexRecord, package: CapturePackage, rebuild_projection: bool = True
    ) -> None:
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
                "object_digest, object_path, transfer_syntax_uid, rows, columns, object_size, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                        item.size,
                        record.created_at.isoformat(),
                    )
                    for item in record.objects
                ),
            )
            if rebuild_projection:
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
                        int(event.get("event_version", 1)),  # pyright: ignore[reportArgumentType]
                        str(event.get("observed_at", record.created_at.isoformat())),
                        int(event.get("monotonic_ns", sequence)),  # pyright: ignore[reportArgumentType]
                        str(event.get("origin", "capture")),
                        event["_raw_json"],
                    ),
                )

    def _rebuild_projection(self) -> None:
        with self.databases.index.write_transaction() as connection:
            rebuild_study_projection(connection)

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
    errors: list[str] | None = None,
) -> tuple[tuple[CapturePackage, Path], ...]:
    """Discover directories and materialize dropped archives into the primary root."""
    primary_root = primary_root.expanduser().resolve()
    primary_root.mkdir(parents=True, exist_ok=True)
    discovered: dict[str, tuple[CapturePackage, Path]] = {}
    for root in (primary_root, *(path.expanduser().resolve() for path in additional_roots)):
        if not root.is_dir():
            continue
        for candidate in sorted(root.iterdir(), key=lambda path: path.name):
            try:
                if candidate.is_dir() and (candidate / "manifest.json").is_file():
                    package = CapturePackage.open(candidate)
                    discovered.setdefault(package.manifest.capture_id, (package, root))
                elif candidate.is_file() and candidate.suffix.lower() == ".lpcap":
                    package, source_root = _materialize_archive(candidate, primary_root)
                    discovered.setdefault(package.manifest.capture_id, (package, source_root))
            except (CaptureFormatError, OSError, ValueError) as exc:
                if errors is None:
                    raise
                errors.append(f"{candidate}: {type(exc).__name__}: {exc}")
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
