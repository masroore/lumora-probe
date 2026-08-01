"""Read-only study projections and cross-capture deletion cascades."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from lumora_probe.core.config import is_uuid7
from lumora_probe.core.errors import LumoraError, PathSecurityError
from lumora_probe.core.paths import assert_contained
from lumora_probe.core.storage import StorageDatabases, rebuild_study_projection
from lumora_probe.shared.events import EventClock, EventIdGenerator

from .contracts import DicomObjectSource


@dataclass(frozen=True, slots=True)
class StudyProjection:
    study_uid: str
    first_seen_at: datetime
    last_seen_at: datetime
    capture_count: int
    instance_count: int
    partial: bool


@dataclass(frozen=True, slots=True)
class SeriesProjection:
    study_uid: str
    series_uid: str
    first_seen_at: datetime
    last_seen_at: datetime
    capture_count: int
    instance_count: int


@dataclass(frozen=True, slots=True)
class InstanceProjection:
    capture_id: str
    study_uid: str
    series_uid: str
    sop_instance_uid: str
    object_digest: str
    object_path: str
    transfer_syntax_uid: str | None
    rows: int | None
    columns: int | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CascadeResult:
    capture_id: str
    affected_study_uids: tuple[str, ...]
    removed_instance_count: int
    removed_bookmark_count: int
    retained_study_uids: tuple[str, ...]
    orphaned_finding_count: int = 0
    orphaned_report_count: int = 0


class StudyProjectionRepository:
    """Query projections and apply the accepted cross-capture deletion semantics."""

    def __init__(
        self,
        databases: StorageDatabases,
        *,
        capture_roots: Iterable[Path] = (),
        clock: object | None = None,
    ) -> None:
        self.databases = databases
        self.capture_roots = tuple(path.expanduser().resolve() for path in capture_roots)
        self.clock = clock

    async def list_studies(self) -> tuple[StudyProjection, ...]:
        rows = await self.databases.index.execute_read(
            "SELECT study_uid, first_seen_at, last_seen_at, capture_count, instance_count, partial "
            "FROM studies ORDER BY study_uid"
        )
        return tuple(
            StudyProjection(
                study_uid=row["study_uid"],
                first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
                last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
                capture_count=row["capture_count"],
                instance_count=row["instance_count"],
                partial=bool(row["partial"]),
            )
            for row in rows
        )

    async def list_series(self, study_uid: str | None = None) -> tuple[SeriesProjection, ...]:
        if study_uid is None:
            sql = (
                "SELECT study_uid, series_uid, first_seen_at, last_seen_at, capture_count, instance_count "
                "FROM series ORDER BY study_uid, series_uid"
            )
            parameters: tuple[object, ...] = ()
        else:
            sql = (
                "SELECT study_uid, series_uid, first_seen_at, last_seen_at, capture_count, instance_count "
                "FROM series WHERE study_uid = ? ORDER BY series_uid"
            )
            parameters = (study_uid,)
        rows = await self.databases.index.execute_read(sql, parameters)
        return tuple(
            SeriesProjection(
                study_uid=row["study_uid"],
                series_uid=row["series_uid"],
                first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
                last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
                capture_count=row["capture_count"],
                instance_count=row["instance_count"],
            )
            for row in rows
        )

    async def list_instances(
        self,
        *,
        study_uid: str | None = None,
        capture_id: str | None = None,
    ) -> tuple[InstanceProjection, ...]:
        clauses: list[str] = []
        parameters: list[object] = []
        if study_uid is not None:
            clauses.append("study_uid = ?")
            parameters.append(study_uid)
        if capture_id is not None:
            clauses.append("capture_id = ?")
            parameters.append(capture_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = await self.databases.index.execute_read(
            "SELECT capture_id, study_uid, series_uid, sop_instance_uid, object_digest, object_path, "
            "transfer_syntax_uid, rows, columns, created_at FROM instances"
            f"{where} ORDER BY study_uid, series_uid, sop_instance_uid, capture_id",
            tuple(parameters),
        )
        return tuple(
            InstanceProjection(
                capture_id=row["capture_id"],
                study_uid=row["study_uid"],
                series_uid=row["series_uid"],
                sop_instance_uid=row["sop_instance_uid"],
                object_digest=row["object_digest"],
                object_path=row["object_path"],
                transfer_syntax_uid=row["transfer_syntax_uid"],
                rows=row["rows"],
                columns=row["columns"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        )

    async def delete_capture(
        self,
        capture_id: str,
        *,
        remove_artifact: bool = True,
    ) -> CascadeResult:
        """Delete one capture and recompute all cross-capture projections."""
        if not is_uuid7(capture_id):
            raise PathSecurityError(
                code="LUMORA-STUDY-CASCADE-001",
                message=f"Invalid capture_id: {capture_id!r}",
                remediation="Use the UUIDv7 capture identifier returned by the capture API.",
                context={"capture_id": capture_id},
            )
        return await asyncio.to_thread(self._delete_capture, capture_id, remove_artifact)

    def _delete_capture(self, capture_id: str, remove_artifact: bool) -> CascadeResult:
        with self.databases.index.connection(read_only=True) as connection:
            capture_row = connection.execute(
                "SELECT path FROM captures WHERE capture_id = ?", (capture_id,)
            ).fetchone()
            if capture_row is None:
                raise KeyError(f"capture not indexed: {capture_id}")
            affected_rows = connection.execute(
                "SELECT DISTINCT study_uid FROM instances WHERE capture_id = ? ORDER BY study_uid",
                (capture_id,),
            ).fetchall()
            removed_instance_count = connection.execute(
                "SELECT COUNT(*) FROM instances WHERE capture_id = ?", (capture_id,)
            ).fetchone()[0]
            capture_path = Path(capture_row["path"]).expanduser().resolve()

        if remove_artifact:
            if not self.capture_roots:
                raise PathSecurityError(
                    code="LUMORA-STUDY-CASCADE-002",
                    message="Capture deletion has no configured capture root",
                    remediation="Configure the writable captures root before deleting evidence.",
                    context={"capture_id": capture_id},
                )
            if not any(_is_contained(capture_path, root) for root in self.capture_roots):
                raise PathSecurityError(
                    code="LUMORA-STUDY-CASCADE-003",
                    message="Capture path is outside configured capture roots",
                    remediation="Refuse deletion of captures outside the configured writable roots.",
                    context={"capture_id": capture_id, "path": str(capture_path)},
                )
            if capture_path.exists():
                shutil.rmtree(capture_path)

        with self.databases.index.write_transaction() as connection:
            connection.execute("DELETE FROM captures WHERE capture_id = ?", (capture_id,))
            rebuild_study_projection(connection)
            retained_rows = connection.execute(
                "SELECT DISTINCT study_uid FROM instances WHERE study_uid IN "
                "(SELECT study_uid FROM studies) ORDER BY study_uid"
            ).fetchall()

        with self.databases.app.write_transaction() as connection:
            removed_bookmark_count = connection.execute(
                "DELETE FROM bookmarks WHERE capture_id = ?", (capture_id,)
            ).rowcount
            payload = {
                "capture_id": capture_id,
                "affected_study_uids": [row["study_uid"] for row in affected_rows],
                "removed_instance_count": removed_instance_count,
                "removed_bookmark_count": removed_bookmark_count,
                "orphaned_finding_count": 0,
                "orphaned_report_count": 0,
                "semantics": "capture-scoped bookmarks delete; study bookmarks retain",
            }
            connection.execute(
                "INSERT INTO audit_log(event_type, entity_type, entity_id, occurred_at, payload_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "CaptureDeleted",
                    "capture",
                    capture_id,
                    _clock_now(self.clock).isoformat(),
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                ),
            )

        return CascadeResult(
            capture_id=capture_id,
            affected_study_uids=tuple(row["study_uid"] for row in affected_rows),
            removed_instance_count=removed_instance_count,
            removed_bookmark_count=removed_bookmark_count,
            retained_study_uids=tuple(row["study_uid"] for row in retained_rows),
        )


def _clock_now(clock: object | None) -> datetime:
    if clock is not None and hasattr(clock, "now"):
        value = clock.now()
        if isinstance(value, datetime):
            return value
    return datetime.now(UTC)


def _is_contained(path: Path, root: Path) -> bool:
    try:
        assert_contained(path, root)
    except PathSecurityError:
        return False
    return True


class InstanceSourceRepository(Protocol):
    """Application composition seam for verified capture-owned DICOM objects."""

    async def get_instance_source(self, instance_id: str) -> DicomObjectSource | None: ...


class InMemoryInstanceSourceRepository:
    """Deterministic source provider used by tests and lightweight app assembly."""

    def __init__(self, sources: Mapping[str, DicomObjectSource] | None = None) -> None:
        self._sources = dict(sources or {})

    async def get_instance_source(self, instance_id: str) -> DicomObjectSource | None:
        return self._sources.get(instance_id)


_logger = logging.getLogger(__name__)


class FileSystemInstanceSourceRepository:
    """Resolve instance IDs to verified capture-owned DICOM bytes."""

    def __init__(
        self,
        captures_root: Path,
        databases: StorageDatabases,
        *,
        capture_roots: Iterable[Path] = (),
    ) -> None:
        self._captures_root = captures_root.expanduser().resolve()
        self._capture_roots = (
            self._captures_root,
            *(path.expanduser().resolve() for path in capture_roots),
        )
        self._databases = databases

    async def get_instance_source(self, instance_id: str) -> DicomObjectSource | None:
        """Look up the projection row, read bytes off-loop, and verify the digest."""
        rows = await self._databases.index.execute_read(
            "SELECT i.capture_id, i.object_digest, i.object_path, c.path AS capture_path "
            "FROM instances AS i JOIN captures AS c ON c.capture_id = i.capture_id "
            "WHERE i.sop_instance_uid = ? LIMIT 1",
            (instance_id,),
        )
        if not rows:
            return None
        row = rows[0]
        capture_id = row["capture_id"]
        digest = row["object_digest"]
        try:
            capture_path_value = row["capture_path"]
        except (KeyError, IndexError):
            capture_path_value = None
        capture_path = (
            Path(capture_path_value).expanduser().resolve()
            if capture_path_value
            else self._captures_root / capture_id
        )
        if not any(
            capture_path == root or root in capture_path.parents for root in self._capture_roots
        ):
            _logger.error(
                "capture source path escapes configured roots", extra={"path": str(capture_path)}
            )
            return None
        object_path = assert_contained(capture_path / row["object_path"], capture_path)
        try:
            raw_bytes = await asyncio.to_thread(object_path.read_bytes)
        except FileNotFoundError:
            _logger.warning(
                "capture object missing",
                extra={"capture_id": capture_id, "digest": digest},
            )
            return None
        actual_digest = hashlib.sha256(raw_bytes).hexdigest()
        if actual_digest != digest:
            _logger.error(
                "capture object digest mismatch; refusing to serve unverified bytes",
                extra={
                    "capture_id": capture_id,
                    "expected": digest,
                    "actual": actual_digest,
                },
            )
            return None
        return DicomObjectSource(
            object_digest=digest,
            raw_bytes=raw_bytes,
            capture_id=capture_id,
            instance_id=instance_id,
        )


@dataclass(frozen=True, slots=True)
class Bookmark:
    """A user-saved study/series navigation point."""

    bookmark_id: str
    name: str
    study_uid: str
    series_uid: str | None
    capture_id: str | None
    sop_instance_uid: str | None
    created_at: datetime


class BookmarkRepository:
    """CRUD for the bookmarks table in app.db."""

    def __init__(
        self,
        databases: StorageDatabases,
        clock: EventClock,
        id_generator: EventIdGenerator,
    ) -> None:
        self._databases = databases
        self._clock = clock
        self._ids = id_generator

    async def add_bookmark(
        self,
        name: str,
        study_uid: str,
        series_uid: str | None = None,
        capture_id: str | None = None,
        sop_instance_uid: str | None = None,
    ) -> Bookmark:
        """Insert a bookmark; raise LumoraError on UNIQUE(name) conflict."""
        bookmark_id = self._ids.new_id()
        created_at = self._clock.now()
        try:
            await asyncio.to_thread(
                self._insert,
                bookmark_id,
                name,
                study_uid,
                series_uid,
                capture_id,
                sop_instance_uid,
                created_at,
            )
        except Exception as error:
            if "UNIQUE" in str(error).upper():
                raise LumoraError(
                    code="LUMORA-STUDIES-BOOKMARKS-001",
                    message=f"A bookmark named '{name}' already exists.",
                    remediation="Choose a different bookmark name.",
                    context={"name": name},
                ) from error
            raise
        return Bookmark(
            bookmark_id=bookmark_id,
            name=name,
            study_uid=study_uid,
            series_uid=series_uid,
            capture_id=capture_id,
            sop_instance_uid=sop_instance_uid,
            created_at=created_at,
        )

    def _insert(
        self,
        bookmark_id: str,
        name: str,
        study_uid: str,
        series_uid: str | None,
        capture_id: str | None,
        sop_instance_uid: str | None,
        created_at: datetime,
    ) -> None:
        with self._databases.app.write_transaction() as conn:
            conn.execute(
                "INSERT INTO bookmarks "
                "(bookmark_id, name, study_uid, series_uid, capture_id, sop_instance_uid, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    bookmark_id,
                    name,
                    study_uid,
                    series_uid,
                    capture_id,
                    sop_instance_uid,
                    created_at.isoformat(),
                ),
            )

    async def list_bookmarks(self, capture_id: str | None = None) -> tuple[Bookmark, ...]:
        """List all bookmarks, optionally filtered by capture_id."""
        return await asyncio.to_thread(self._list, capture_id)

    def _list(self, capture_id: str | None) -> tuple[Bookmark, ...]:
        with self._databases.app.connection(read_only=True) as conn:
            if capture_id is not None:
                rows = conn.execute(
                    "SELECT bookmark_id, name, study_uid, series_uid, capture_id, "
                    "sop_instance_uid, created_at FROM bookmarks "
                    "WHERE capture_id = ? ORDER BY created_at",
                    (capture_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT bookmark_id, name, study_uid, series_uid, capture_id, "
                    "sop_instance_uid, created_at FROM bookmarks ORDER BY created_at"
                ).fetchall()
        return tuple(self._row_to_bookmark(row) for row in rows)

    async def remove_bookmark(self, bookmark_id: str) -> bool:
        """Delete a bookmark by ID; return True if it existed."""
        return await asyncio.to_thread(self._remove, bookmark_id)

    def _remove(self, bookmark_id: str) -> bool:
        with self._databases.app.write_transaction() as conn:
            cursor = conn.execute("DELETE FROM bookmarks WHERE bookmark_id = ?", (bookmark_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_bookmark(row: Any) -> Bookmark:
        return Bookmark(
            bookmark_id=row[0],
            name=row[1],
            study_uid=row[2],
            series_uid=row[3],
            capture_id=row[4],
            sop_instance_uid=row[5],
            created_at=datetime.fromisoformat(row[6]),
        )


__all__: tuple[str, ...] = ()
