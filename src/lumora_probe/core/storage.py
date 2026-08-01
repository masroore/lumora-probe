# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""SQLite storage primitives and schemas for the rebuildable index and app database."""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from collections.abc import Generator, Iterable, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .paths import DataPaths, assert_local_filesystem, is_network_filesystem

INDEX_SCHEMA_VERSION = 1
APP_SCHEMA_VERSION = 1
DEFAULT_BUSY_TIMEOUT_MS = 5_000


class DatabaseKind(StrEnum):
    """Physical database roles with different durability semantics."""

    INDEX = "index"
    APP = "app"


_INDEX_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS captures (
    capture_id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    source_root TEXT NOT NULL,
    format_version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    state TEXT NOT NULL,
    fidelity TEXT NOT NULL,
    partial INTEGER NOT NULL CHECK (partial IN (0, 1)),
    promoted_from_buffer INTEGER NOT NULL CHECK (promoted_from_buffer IN (0, 1)),
    interruption_reason TEXT,
    manifest_sha256 TEXT NOT NULL,
    indexed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS studies (
    study_uid TEXT PRIMARY KEY,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    capture_count INTEGER NOT NULL DEFAULT 0,
    instance_count INTEGER NOT NULL DEFAULT 0,
    partial INTEGER NOT NULL CHECK (partial IN (0, 1))
);

CREATE TABLE IF NOT EXISTS series (
    study_uid TEXT NOT NULL,
    series_uid TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    capture_count INTEGER NOT NULL DEFAULT 0,
    instance_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (study_uid, series_uid),
    FOREIGN KEY (study_uid) REFERENCES studies(study_uid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS instances (
    instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id TEXT NOT NULL,
    study_uid TEXT NOT NULL,
    series_uid TEXT NOT NULL,
    sop_instance_uid TEXT NOT NULL,
    object_digest TEXT NOT NULL,
    object_path TEXT NOT NULL,
    transfer_syntax_uid TEXT,
    rows INTEGER,
    columns INTEGER,
    object_size INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE (capture_id, study_uid, series_uid, sop_instance_uid, object_digest),
    FOREIGN KEY (capture_id) REFERENCES captures(capture_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS event_window (
    capture_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    event_name TEXT NOT NULL,
    event_version INTEGER NOT NULL,
    observed_at TEXT NOT NULL,
    monotonic_ns INTEGER NOT NULL,
    origin TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (capture_id, sequence),
    UNIQUE (capture_id, event_id),
    FOREIGN KEY (capture_id) REFERENCES captures(capture_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_captures_created_at ON captures(created_at);
CREATE INDEX IF NOT EXISTS idx_captures_state_created_id ON captures(state, created_at, capture_id);
CREATE INDEX IF NOT EXISTS idx_instances_study ON instances(study_uid);
CREATE INDEX IF NOT EXISTS idx_instances_series ON instances(study_uid, series_uid);
CREATE INDEX IF NOT EXISTS idx_instances_sop ON instances(sop_instance_uid);
CREATE INDEX IF NOT EXISTS idx_instances_created_id ON instances(created_at, instance_id);
CREATE INDEX IF NOT EXISTS idx_event_window_event_name ON event_window(capture_id, event_name);
CREATE INDEX IF NOT EXISTS idx_event_window_observed ON event_window(observed_at, capture_id, sequence);
"""

_APP_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    operation_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    state TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    outcome TEXT,
    progress_json TEXT NOT NULL,
    interruption_reason TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookmarks (
    bookmark_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    study_uid TEXT,
    series_uid TEXT,
    capture_id TEXT,
    sop_instance_uid TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (name)
);

CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS idx_jobs_started_at ON jobs(started_at);
CREATE INDEX IF NOT EXISTS idx_audit_occurred_at ON audit_log(occurred_at);
CREATE INDEX IF NOT EXISTS idx_bookmarks_capture ON bookmarks(capture_id);
"""


@dataclass(frozen=True, slots=True)
class SQLiteConnectionPolicy:
    """Connection settings shared by both physical SQLite databases."""

    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
    synchronous: str = "NORMAL"
    wal: bool = True

    def __post_init__(self) -> None:
        if self.busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must not be negative")
        if self.synchronous not in {"OFF", "NORMAL", "FULL", "EXTRA"}:
            raise ValueError("unsupported SQLite synchronous mode")

    def connect(self, path: Path, *, read_only: bool = False) -> sqlite3.Connection:
        """Open a configured SQLite connection and apply safety pragmas."""
        path = path.expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        if read_only:
            connection = sqlite3.connect(
                f"file:{path}?mode=ro", uri=True, timeout=self.busy_timeout_ms / 1000
            )
        else:
            connection = sqlite3.connect(
                path, timeout=self.busy_timeout_ms / 1000, check_same_thread=False
            )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        connection.execute(f"PRAGMA synchronous = {self.synchronous}")
        if self.wal and not read_only:
            connection.execute("PRAGMA journal_mode = WAL")
        return connection


class SQLiteDatabase:
    """A small single-writer facade over a SQLite database file."""

    def __init__(
        self,
        path: Path,
        kind: DatabaseKind,
        *,
        policy: SQLiteConnectionPolicy | None = None,
        network_detector: Any | None = None,
    ) -> None:
        self.path = path.expanduser().resolve()
        self.kind = DatabaseKind(kind)
        self.policy = policy or SQLiteConnectionPolicy()
        assert_local_filesystem(
            (self.path,),
            detector=network_detector or is_network_filesystem,
        )
        self._writer_lock = threading.RLock()

    @contextmanager
    def connection(self, *, read_only: bool = False) -> Generator[sqlite3.Connection]:
        connection = self.policy.connect(self.path, read_only=read_only)
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def write_transaction(self) -> Generator[sqlite3.Connection]:
        """Serialize writes while retaining SQLite's concurrent reader support."""
        with self._writer_lock, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()

    def initialise(self, *, recreate: bool = False) -> None:
        """Create or migrate the database without discarding derived data by default."""
        if self.kind is DatabaseKind.INDEX:
            if recreate:
                recreate_index_schema(self.path, policy=self.policy)
            else:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with closing(self.policy.connect(self.path)) as connection:
                    connection.executescript(_INDEX_SCHEMA)
                    columns = {row[1] for row in connection.execute("PRAGMA table_info(instances)")}
                    if "object_size" not in columns:
                        connection.execute(
                            "ALTER TABLE instances ADD COLUMN object_size INTEGER NOT NULL DEFAULT 0"
                        )
                    connection.execute(
                        "INSERT INTO schema_metadata(key, value) VALUES ('schema_version', ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (str(INDEX_SCHEMA_VERSION),),
                    )
                    connection.commit()
        else:
            migrate_app_schema(self.path, policy=self.policy)

    async def execute_read(self, sql: str, parameters: Sequence[Any] = ()) -> list[sqlite3.Row]:
        def read() -> list[sqlite3.Row]:
            with self.connection(read_only=self.path.exists()) as connection:
                return list(connection.execute(sql, parameters).fetchall())

        return await asyncio.to_thread(read)

    async def execute_write(self, sql: str, parameters: Sequence[Any] = ()) -> int:
        def write() -> int:
            with self.write_transaction() as connection:
                cursor = connection.execute(sql, parameters)
                return int(cursor.rowcount)

        return await asyncio.to_thread(write)

    async def executemany_write(self, sql: str, parameters: Iterable[Sequence[Any]]) -> int:
        materialized = tuple(parameters)

        def write() -> int:
            with self.write_transaction() as connection:
                cursor = connection.executemany(sql, materialized)
                return int(cursor.rowcount)

        return await asyncio.to_thread(write)


def schema_sql(kind: DatabaseKind) -> str:
    """Return the canonical schema script for a database role."""
    return _INDEX_SCHEMA if DatabaseKind(kind) is DatabaseKind.INDEX else _APP_SCHEMA


def recreate_index_schema(path: Path, *, policy: SQLiteConnectionPolicy | None = None) -> None:
    """Create a fresh rebuildable index schema, replacing any older projection."""
    connection_policy = policy or SQLiteConnectionPolicy()
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connection_policy.connect(path)) as connection:
        connection.executescript(
            "DROP TABLE IF EXISTS event_window; DROP TABLE IF EXISTS instances;"
        )
        connection.executescript("DROP TABLE IF EXISTS series; DROP TABLE IF EXISTS studies;")
        connection.executescript(
            "DROP TABLE IF EXISTS captures; DROP TABLE IF EXISTS schema_metadata;"
        )
        connection.executescript(_INDEX_SCHEMA)
        connection.execute(
            "INSERT INTO schema_metadata(key, value) VALUES ('schema_version', ?)",
            (str(INDEX_SCHEMA_VERSION),),
        )
        connection.commit()


def rebuild_study_projection(connection: sqlite3.Connection) -> None:
    """Recompute Study and Series rows from capture-owned instance rows."""
    connection.execute("DELETE FROM series")
    connection.execute("DELETE FROM studies")
    connection.execute(
        "INSERT INTO studies(study_uid, first_seen_at, last_seen_at, capture_count, "
        "instance_count, partial) SELECT study_uid, MIN(created_at), MAX(created_at), "
        "COUNT(DISTINCT capture_id), COUNT(*), CASE WHEN COUNT(DISTINCT capture_id) > 1 THEN 1 ELSE 0 END "
        "FROM instances GROUP BY study_uid"
    )
    connection.execute(
        "INSERT INTO series(study_uid, series_uid, first_seen_at, last_seen_at, capture_count, instance_count) "
        "SELECT study_uid, series_uid, MIN(created_at), MAX(created_at), COUNT(DISTINCT capture_id), COUNT(*) "
        "FROM instances GROUP BY study_uid, series_uid"
    )


def migrate_app_schema(path: Path, *, policy: SQLiteConnectionPolicy | None = None) -> None:
    """Apply idempotent app database migrations."""
    connection_policy = policy or SQLiteConnectionPolicy()
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connection_policy.connect(path)) as connection:
        connection.executescript(_APP_SCHEMA)
        connection.execute(
            "INSERT INTO schema_metadata(key, value) VALUES ('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(APP_SCHEMA_VERSION),),
        )
        connection.commit()


@dataclass(frozen=True, slots=True)
class StorageDatabases:
    """The two physical databases owned by a data root."""

    index: SQLiteDatabase
    app: SQLiteDatabase

    @classmethod
    def from_paths(
        cls,
        paths: DataPaths,
        *,
        policy: SQLiteConnectionPolicy | None = None,
        network_detector: Any | None = None,
    ) -> StorageDatabases:
        return cls(
            index=SQLiteDatabase(
                paths.index_db,
                DatabaseKind.INDEX,
                policy=policy,
                network_detector=network_detector,
            ),
            app=SQLiteDatabase(
                paths.app_db,
                DatabaseKind.APP,
                policy=policy,
                network_detector=network_detector,
            ),
        )

    def initialise(self, *, recreate_index: bool = False) -> None:
        """Initialise both stores; index recreation is explicit because index rows are recoverable."""
        self.index.initialise(recreate=recreate_index)
        self.app.initialise()


__all__ = [
    "APP_SCHEMA_VERSION",
    "DEFAULT_BUSY_TIMEOUT_MS",
    "INDEX_SCHEMA_VERSION",
    "DatabaseKind",
    "SQLiteConnectionPolicy",
    "SQLiteDatabase",
    "StorageDatabases",
    "migrate_app_schema",
    "rebuild_study_projection",
    "recreate_index_schema",
    "schema_sql",
]
