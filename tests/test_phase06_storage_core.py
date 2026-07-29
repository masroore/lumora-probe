from __future__ import annotations

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from lumora_probe.core.config import StartupConfig
from lumora_probe.core.errors import NetworkFilesystemError
from lumora_probe.core.paths import DataPaths
from lumora_probe.core.storage import (
    DatabaseKind,
    SQLiteDatabase,
    StorageDatabases,
    migrate_app_schema,
    recreate_index_schema,
)


def test_physical_databases_have_separate_rebuildable_and_authoritative_schemas(
    tmp_path: Path,
) -> None:
    paths = DataPaths.from_config(StartupConfig(data_dir=tmp_path / "data"))
    paths.initialise(network_detector=lambda _: False)
    databases = StorageDatabases.from_paths(paths, network_detector=lambda _: False)
    databases.initialise()

    with sqlite3.connect(paths.index_db) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {"captures", "studies", "series", "instances", "event_window"} <= tables
    assert "jobs" not in tables

    with sqlite3.connect(paths.app_db) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {"jobs", "audit_log", "bookmarks"} <= tables
    assert "captures" not in tables


def test_index_recreation_drops_stale_projection_but_app_migration_preserves_history(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "index.db"
    app_path = tmp_path / "app.db"
    recreate_index_schema(index_path)
    migrate_app_schema(app_path)

    with sqlite3.connect(index_path) as connection:
        connection.execute(
            "INSERT INTO captures VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "capture-1",
                "/captures/capture-1",
                "/captures",
                1,
                "2026-07-29T00:00:00+00:00",
                None,
                "completed",
                "events",
                0,
                0,
                None,
                "digest",
                "2026-07-29T00:00:00+00:00",
            ),
        )
        connection.commit()
    with sqlite3.connect(app_path) as connection:
        connection.execute(
            "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("job-1", "rebuild", "{}", "completed", "now", "now", "ok", "{}", None),
        )
        connection.commit()

    recreate_index_schema(index_path)
    migrate_app_schema(app_path)

    with sqlite3.connect(index_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM captures").fetchone() == (0,)
    with sqlite3.connect(app_path) as connection:
        assert connection.execute("SELECT operation_id FROM jobs").fetchone() == ("job-1",)


def test_connection_policy_enables_wal_and_busy_timeout(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "index.db", DatabaseKind.INDEX)
    database.initialise()
    with database.connection() as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5_000
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_sqlite_path_on_network_filesystem_is_refused(tmp_path: Path) -> None:
    with pytest.raises(NetworkFilesystemError):
        SQLiteDatabase(
            tmp_path / "index.db",
            DatabaseKind.INDEX,
            network_detector=lambda _: True,
        )


def test_one_writer_supports_concurrent_readers(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "app.db", DatabaseKind.APP)
    database.initialise()

    def write_job(number: int) -> None:
        with database.write_transaction() as connection:
            connection.execute(
                "INSERT INTO jobs(operation_id, job_type, parameters_json, state, started_at, "
                "progress_json) VALUES (?, ?, ?, ?, ?, ?)",
                (f"job-{number}", "spike", "{}", "completed", str(number), "{}"),
            )

    def read_count() -> int:
        with database.connection(read_only=True) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])

    with ThreadPoolExecutor(max_workers=8) as executor:
        writes = list(executor.map(write_job, range(40)))
        assert len(writes) == 40
        counts = list(executor.map(lambda _: read_count(), range(40)))

    assert counts[-1] == 40
    with database.connection(read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 40


@pytest.mark.asyncio
async def test_async_write_and_read_facade_uses_worker_threads(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "app.db", DatabaseKind.APP)
    database.initialise()
    await database.execute_write(
        "INSERT INTO audit_log(event_type, entity_type, occurred_at, payload_json) "
        "VALUES (?, ?, ?, ?)",
        ("StorageTested", "storage", "now", "{}"),
    )
    rows = await database.execute_read("SELECT event_type FROM audit_log")
    assert [row["event_type"] for row in rows] == ["StorageTested"]
    await asyncio.sleep(0)
