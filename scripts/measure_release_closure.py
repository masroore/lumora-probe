"""Measure the ratified release-closure pagination, rebuild, and ring gates."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import platform
import sqlite3
import tempfile
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from lumora_probe.bootstrap import (
    _LiveEvidenceStore,  # pyright: ignore[reportPrivateUsage]
    _SQLiteResourceStore,  # pyright: ignore[reportPrivateUsage]
)
from lumora_probe.captures.format import CaptureFidelity, CaptureManifest
from lumora_probe.captures.repository import CaptureRepository
from lumora_probe.captures.service import RingBufferConfig, RingBufferService
from lumora_probe.core.config import StartupConfig
from lumora_probe.core.paths import DataPaths
from lumora_probe.core.storage import (
    SQLiteConnectionPolicy,
    StorageDatabases,
    rebuild_study_projection,
)


@dataclass(frozen=True, slots=True)
class Workload:
    """Deterministic production-scale projection workload."""

    captures: int = 10_000
    instances: int = 100_000
    events: int = 500_000


@dataclass(slots=True)
class TraceMetrics:
    """SQLite trace counters scoped to one measured operation."""

    statements: int = 0
    sql_bytes: int = 0

    def reset(self) -> None:
        self.statements = 0
        self.sql_bytes = 0

    def record(self, statement: str) -> None:
        self.statements += 1
        self.sql_bytes += len(statement.encode("utf-8"))


class BenchmarkClock:
    """Fixed clock for deterministic synthetic persistence workloads."""

    def now(self) -> datetime:
        return datetime(2026, 8, 1, tzinfo=UTC)

    def monotonic_ns(self) -> int:
        return 0


class TracingPolicy:
    """Connection policy that adds narrow per-connection SQLite trace counters."""

    def __init__(self, metrics: TraceMetrics) -> None:
        self._base = SQLiteConnectionPolicy()
        self._metrics = metrics
        self.busy_timeout_ms = self._base.busy_timeout_ms
        self.synchronous = self._base.synchronous
        self.wal = self._base.wal

    def connect(self, path: Path, *, read_only: bool = False) -> sqlite3.Connection:
        connection = self._base.connect(path, read_only=read_only)
        connection.set_trace_callback(self._metrics.record)
        return connection


def _uuid7(index: int) -> str:
    """Return a deterministic UUIDv7 for synthetic benchmark manifests."""
    timestamp_ms = 1_722_470_400_000 + index
    value = (
        ((timestamp_ms & ((1 << 48) - 1)) << 80)
        | (0x7 << 76)
        | ((index & 0xFFF) << 64)
        | (0b10 << 62)
        | (index & ((1 << 62) - 1))
    )
    return str(UUID(int=value))


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(len(ordered) * percentile)) - 1
    return ordered[rank]


def _summary(samples: list[float]) -> dict[str, Any]:
    return {
        "samples_ms": [round(value, 3) for value in samples],
        "median_ms": round(_percentile(samples, 0.5), 3),
        "p95_ms": round(_percentile(samples, 0.95), 3),
    }


def _local_network_detector(_path: Path) -> bool:
    return False


def _storage(
    root: Path, *, metrics: TraceMetrics | None = None
) -> tuple[DataPaths, StorageDatabases]:
    paths = DataPaths.from_config(StartupConfig(data_dir=root))
    paths.initialise(network_detector=_local_network_detector)
    policy = TracingPolicy(metrics) if metrics is not None else None
    storage = StorageDatabases.from_paths(
        paths,
        policy=policy,  # type: ignore[arg-type]
        network_detector=_local_network_detector,
    )
    storage.initialise()
    return paths, storage


def _populate_projection(
    storage: StorageDatabases,
    paths: DataPaths,
    workload: Workload,
) -> None:
    timestamp = "2026-08-01T00:00:00+00:00"
    with storage.index.write_transaction() as connection:
        connection.executemany(
            "INSERT INTO captures VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                (
                    f"cap-{index:05d}",
                    str(paths.captures / f"cap-{index:05d}"),
                    str(paths.captures),
                    1,
                    timestamp,
                    timestamp,
                    "completed",
                    "objects",
                    0,
                    0,
                    None,
                    f"{index:064x}",
                    timestamp,
                )
                for index in range(workload.captures)
            ),
        )
        connection.executemany(
            "INSERT INTO instances(capture_id,study_uid,series_uid,sop_instance_uid,"
            "object_digest,object_path,transfer_syntax_uid,rows,columns,object_size,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                (
                    f"cap-{index // 10:05d}",
                    f"study-{index % 100:03d}",
                    f"series-{index % 1000:04d}",
                    f"sop-{index:06d}",
                    f"{index:064x}",
                    f"objects/{index:064x}",
                    "1.2.840.10008.1.2.1",
                    None,
                    None,
                    128,
                    timestamp,
                )
                for index in range(workload.instances)
            ),
        )
        connection.executemany(
            "INSERT INTO event_window(capture_id,sequence,event_id,event_name,event_version,"
            "observed_at,monotonic_ns,origin,raw_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                (
                    f"cap-{index // 50:05d}",
                    index % 50,
                    f"evt-{index:07d}",
                    "ObservedEvent" if index % 2 else "CStoreReceived",
                    1,
                    timestamp,
                    index,
                    "observed",
                    json.dumps(
                        {
                            "event_id": f"evt-{index:07d}",
                            "event_name": "ObservedEvent" if index % 2 else "CStoreReceived",
                            "capture_id": f"cap-{index // 50:05d}",
                            "sequence": index % 50,
                            "aggregate_type": "Capture",
                            "aggregate_id": f"cap-{index // 50:05d}",
                            "origin": "observed",
                        },
                        separators=(",", ":"),
                    ),
                )
                for index in range(workload.events)
            ),
        )
        rebuild_study_projection(connection)


def _make_manifest_root(root: Path, count: int) -> Path:
    captures = root / "captures"
    timestamp = datetime(2026, 8, 1, tzinfo=UTC)
    for index in range(count):
        capture_path = captures / f"capture-{index:05d}"
        (capture_path / "objects").mkdir(parents=True)
        manifest = CaptureManifest(
            capture_id=_uuid7(index),
            created_at=timestamp + timedelta(seconds=index),
            completed_at=timestamp + timedelta(seconds=index),
            fidelity=CaptureFidelity.OBJECTS,
        )
        (capture_path / "manifest.json").write_bytes(
            manifest.model_dump_json(exclude_none=False).encode("utf-8") + b"\n"
        )
    return captures


async def _measure_pages(storage: StorageDatabases, paths: DataPaths) -> dict[str, Any]:
    projection = _SQLiteResourceStore(storage)

    class EmptyRing:
        def snapshot(self) -> tuple[object, ...]:
            return ()

    ring = EmptyRing()
    events = _LiveEvidenceStore(storage, ring)
    captures = CaptureRepository(
        storage,
        clock=BenchmarkClock(),
    )
    cases: dict[str, Callable[[], Awaitable[tuple[tuple[Any, ...], int]]]] = {
        "captures_first_50": lambda: captures.list_captures_page(
            offset=0, limit=50, sort="created_at,capture_id"
        ),
        "captures_middle_500": lambda: captures.list_captures_page(
            offset=5_000, limit=500, sort="created_at,capture_id"
        ),
        "captures_final_500": lambda: captures.list_captures_page(
            offset=9_500, limit=500, sort="-created_at,capture_id"
        ),
        "instances_first_50": lambda: projection.list_page(
            "instances", offset=0, limit=50, sort="created_at"
        ),
        "instances_middle_500": lambda: projection.list_page(
            "instances", offset=50_000, limit=500, sort="created_at"
        ),
        "instances_sort_filter_500": lambda: projection.list_page(
            "instances",
            offset=0,
            limit=500,
            sort="sop_instance_uid",
            filter="study_uid:study-050",
        ),
        "events_first_50": lambda: events.list_page(
            "events", offset=0, limit=50, sort="capture_id,sequence"
        ),
        "events_middle_500": lambda: events.list_page(
            "events", offset=250_000, limit=500, sort="capture_id,sequence"
        ),
        "events_sort_filter_500": lambda: events.list_page(
            "events",
            offset=0,
            limit=500,
            sort="capture_id,sequence",
            filter="event_name:CStoreReceived",
        ),
    }
    result: dict[str, Any] = {}
    for name, operation in cases.items():
        await operation()
        samples: list[float] = []
        total = 0
        rows = 0
        for _ in range(5):
            started = time.perf_counter()
            page, total = await operation()
            samples.append((time.perf_counter() - started) * 1000)
            rows = len(page)
        result[name] = {**_summary(samples), "rows": rows, "total": total}
    return result


async def _measure_rebuild(root: Path, count: int) -> dict[str, Any]:
    metrics = TraceMetrics()
    paths, storage = _storage(root, metrics=metrics)
    captures = _make_manifest_root(root, count)
    repository = CaptureRepository(
        storage,
        clock=BenchmarkClock(),
    )
    await repository.rebuild(captures)
    samples: list[float] = []
    traces: list[dict[str, int]] = []
    for _ in range(5):
        metrics.reset()
        started = time.perf_counter()
        records = await repository.rebuild(captures)
        samples.append((time.perf_counter() - started) * 1000)
        traces.append(
            {
                "records": len(records),
                "statements": metrics.statements,
                "sql_bytes": metrics.sql_bytes,
            }
        )
    return {
        **_summary(samples),
        "count": count,
        "traces": traces,
        "index_bytes": paths.index_db.stat().st_size,
    }


async def _measure_ring(root: Path) -> dict[str, Any]:
    target = 8 * 1024 * 1024
    raw = b'{"payload":"' + b"x" * (32 * 1024) + b'"}'
    samples: list[float] = []
    details: list[dict[str, Any]] = []
    for sample in range(5):
        sample_root = root / f"ring-{sample}"
        clock = BenchmarkClock()
        ring = RingBufferService(
            config=RingBufferConfig(max_bytes=target * 2, retention_seconds=3600),
            clock=clock,
            root=sample_root,
        )
        started = time.perf_counter()
        count = math.ceil(target * 12 / len(raw))
        for index in range(count):
            ring.record_event_raw(raw, occurred_at=clock.now(), monotonic_ns=index)
        await ring.stop()
        samples.append((time.perf_counter() - started) * 1000)
        stats = dict(ring.persistence_stats)
        details.append(
            {
                "records": count,
                "accepted_bytes": count * len(raw),
                "stats": stats,
                "amplification": (stats["append_bytes"] + stats["compaction_bytes"])
                / (count * len(raw)),
            }
        )
    return {**_summary(samples), "segment_target_bytes": target, "samples": details}


def _validate(results: Mapping[str, Any]) -> None:
    page_limits = {
        name: 250 if name.startswith(("captures_", "instances_")) else 500
        for name in results["pagination"]
    }
    failures = [
        f"{name} p95 {value['p95_ms']:.3f}ms > {page_limits[name]}ms"
        for name, value in results["pagination"].items()
        if value["p95_ms"] > page_limits[name]
    ]
    rebuild = results["rebuild"]
    if rebuild["10k"]["p95_ms"] > 60_000:
        failures.append("10k rebuild p95 exceeds 60s")
    if rebuild["2n_median_ratio"] > 3:
        failures.append(f"2N rebuild median ratio {rebuild['2n_median_ratio']:.3f} exceeds 3")
    ring = results["ring"]
    if max(item["amplification"] for item in ring["samples"]) > 4:
        failures.append("ring write amplification exceeds 4x")
    if failures:
        raise SystemExit("release-closure performance gate failed: " + "; ".join(failures))


async def _run(workload: Workload) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="lumora-release-closure-") as temporary:
        root = Path(temporary)
        metrics = TraceMetrics()
        paths, storage = _storage(root / "projection", metrics=metrics)
        started = time.perf_counter()
        _populate_projection(storage, paths, workload)
        populate_seconds = time.perf_counter() - started
        pagination = await _measure_pages(storage, paths)
        rebuild_10k = await _measure_rebuild(root / "rebuild-10k", workload.captures)
        rebuild_2n = await _measure_rebuild(root / "rebuild-2n", workload.captures * 2)
        ring = await _measure_ring(root)
        return {
            "commit": _git_commit(),
            "host": {
                "platform": platform.platform(),
                "system": platform.system(),
                "processor": platform.processor(),
                "python": platform.python_version(),
                "sqlite": sqlite3.sqlite_version,
                "filesystem": str(root),
                "pid": os.getpid(),
            },
            "workload": asdict(workload),
            "projection_population_seconds": round(populate_seconds, 3),
            "pagination": pagination,
            "rebuild": {
                "10k": rebuild_10k,
                "2n": rebuild_2n,
                "2n_median_ratio": rebuild_2n["median_ms"] / rebuild_10k["median_ms"],
            },
            "ring": ring,
        }


def _git_commit() -> str:
    try:
        return (
            __import__("subprocess").check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        )
    except (OSError, ValueError):
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write JSON evidence to this path")
    args = parser.parse_args()
    result = asyncio.run(_run(Workload()))
    _validate(result)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
