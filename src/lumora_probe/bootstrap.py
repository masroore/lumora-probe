# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Production composition root for the Phase 17 observable application."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, ClassVar, cast

from fastapi import FastAPI

from lumora_probe.associations.network import DICOMListener, DICOMListenerConfig
from lumora_probe.captures.repository import CaptureRepository
from lumora_probe.captures.service import CaptureEngine, RingBufferService
from lumora_probe.core.alerts import AlertRegistry, AlertThresholds
from lumora_probe.core.audit import AuditCategory, AuditLog
from lumora_probe.core.bus import EventBus
from lumora_probe.core.clock import SystemClock
from lumora_probe.core.config import StartupConfig
from lumora_probe.core.health import HealthRegistry
from lumora_probe.core.lifecycle import LifecycleManager, ServiceHealth
from lumora_probe.core.logging import get_logger, log_operational
from lumora_probe.core.metrics import MetricRegistry
from lumora_probe.core.operations import InMemoryJobRegistry, SQLiteOperationRegistry
from lumora_probe.core.paths import DataPaths
from lumora_probe.core.storage import StorageDatabases
from lumora_probe.plugins.contracts import PluginDiagnostic
from lumora_probe.plugins.repository import PluginRepository
from lumora_probe.plugins.service import PluginService
from lumora_probe.reports.jobs import ReportJobService
from lumora_probe.reports.service import CaptureSummaryService, ReportService
from lumora_probe.settings.runtime import RuntimeSettingsStore
from lumora_probe.shared.events import EventEnvelope
from lumora_probe.studies.domain import DecodeError
from lumora_probe.studies.repository import (
    BookmarkRepository,
    FileSystemInstanceSourceRepository,
    StudyProjectionRepository,
)
from lumora_probe.studies.service import DecodeService, LRUFrameCache, MetadataInspectorService
from lumora_probe.web.api import create_app
from lumora_probe.web.event_routes import EventPageQuery
from lumora_probe.web.live import LiveEventSource
from lumora_probe.web.security import SecurityPolicy
from lumora_probe.web.transfer_inspector import TransferInspectorService


@dataclass(frozen=True, slots=True)
class ProductionRuntime:
    """Composed production graph exposed to process-boundary verification."""

    app: FastAPI
    lifecycle: LifecycleManager
    capture_engine: CaptureEngine
    dicom_listener: DICOMListener
    bus: EventBus
    paths: DataPaths


class PluginServiceAdapter:
    """Adapt domain records to the web mapping contract at the composition root."""

    def __init__(
        self,
        service: PluginService,
        *,
        audit: AuditLog,
        clock: SystemClock,
        metrics: MetricRegistry | None = None,
    ) -> None:
        self.service = service
        self.audit = audit
        self.clock = clock
        self.metrics = metrics

    def records(self) -> Sequence[Mapping[str, Any]]:
        return tuple(record.as_dict() for record in self.service.records())

    def inspect(self, plugin_id: str) -> Mapping[str, Any]:
        return self.service.inspect(plugin_id).as_dict()

    async def set_enabled(self, plugin_id: str, enabled: bool) -> Mapping[str, Any]:
        record = self.service.set_enabled(plugin_id, enabled)
        if self.metrics is not None:
            self.metrics.set_plugin_status(plugin_id, record.status.value)
        await self.audit.append(
            AuditCategory.ADMINISTRATIVE_ACTION,
            entity_type="plugin",
            entity_id=plugin_id,
            occurred_at=self.clock.now(),
            payload={"action": "enable" if enabled else "disable", "plugin": record.as_dict()},
        )
        return record.as_dict()


class HealthRegistryAdapter:
    """Convert core health value objects to the web provider mapping shape."""

    def __init__(self, registry: HealthRegistry) -> None:
        self.registry = registry

    async def check(self) -> Mapping[str, object]:
        return (await self.registry.check()).as_dict()


class AuditedSettingsProvider:
    """Adapt persistent settings and apply supported changes to live services."""

    def __init__(
        self,
        store: RuntimeSettingsStore,
        audit: AuditLog,
        clock: SystemClock,
        *,
        ring_buffer: RingBufferService,
        decode_cache: LRUFrameCache,
        dicom_listener: DICOMListener,
        security_policy: SecurityPolicy,
        base_read_only: bool = False,
    ) -> None:
        self._store = store
        self._audit = audit
        self._clock = clock
        self._ring_buffer = ring_buffer
        self._decode_cache = decode_cache
        self._dicom_listener = dicom_listener
        self._security_policy = security_policy
        self._base_read_only = base_read_only

    async def get(self) -> Mapping[str, Any]:
        return {
            "items": [
                {"name": snapshot.name, "value": snapshot.value, "source": snapshot.source}
                for snapshot in self._store.snapshots()
            ]
        }

    async def update(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        for name, value in values.items():
            self._store.validate_update(name, value)
        previous = {name: self._store.snapshot(name).value for name in values}
        applied: list[str] = []
        try:
            for name, value in values.items():
                self._apply(name, value)
                applied.append(name)
            snapshots = self._store.update_many(values)
        except Exception:
            for name in reversed(applied):
                try:
                    self._apply(name, previous[name])
                except (OSError, TypeError, ValueError, RuntimeError) as rollback_error:
                    log_operational(
                        get_logger("lumora.settings"),
                        "runtime setting rollback failed",
                        level="error",
                        setting=name,
                        error=type(rollback_error).__name__,
                    )
            raise
        await self._audit.append(
            AuditCategory.CONFIGURATION_CHANGE,
            entity_type="runtime-settings",
            occurred_at=self._clock.now(),
            payload={"keys": sorted(values)},
        )
        return {
            "items": [
                {"name": snapshot.name, "value": snapshot.value, "source": snapshot.source}
                for snapshot in snapshots
            ]
        }

    def _apply(self, name: str, value: Any) -> None:
        if name == "ring_buffer_seconds":
            self._ring_buffer.update_config(retention_seconds=float(value))
        elif name == "ring_buffer_max_mb":
            self._ring_buffer.update_config(max_bytes=int(value) * 1024 * 1024)
        elif name == "ring_buffer_events_only":
            self._ring_buffer.update_config(events_only=bool(value))
        elif name == "decode_cache_max_mb":
            self._decode_cache.resize_bytes(int(value) * 1024 * 1024)
        elif name == "ae_allowlist":
            self._dicom_listener.update_allowed_calling_aets(frozenset(value))
        elif name == "ip_allowlist":
            self._dicom_listener.update_allowed_source_ips(frozenset(value))
        elif name == "read_only":
            self._security_policy.update_read_only(self._base_read_only or bool(value))
        elif name in {"theme", "rule_set_toggles"}:
            return


class _CaptureRetentionProvider:
    """Expose ring-buffer status and engine-owned promotion to web routes."""

    def __init__(self, engine: CaptureEngine) -> None:
        self._engine = engine

    def status(self) -> Any:
        return self._engine.ring_buffer.status()

    async def promote_window(self, **kwargs: Any) -> Any:
        return await self._engine.promote_window(**kwargs)


class _CaptureEngineAdapter:
    """Present CaptureEngine as a lifecycle.Service, closing over the event bus."""

    name = "capture-engine"

    def __init__(self, engine: Any, *, event_bus: Any | None) -> None:
        self._engine = engine
        self._bus = event_bus

    async def start(self) -> None:
        await self._engine.start(event_bus=self._bus)

    async def stop(self) -> None:
        await self._engine.stop()

    async def stop_accepting(self) -> None:
        await self._engine.stop_accepting()

    async def drain(self) -> None:
        await self._engine.drain()

    async def flush(self) -> None:
        await self._engine.flush()

    async def interrupt(self, reason: str = "shutdown deadline") -> None:
        await self._engine.interrupt(reason)

    def health(self) -> ServiceHealth:
        return self._engine.health()


class _DefaultExecutorAdapter:
    name = "executor"

    def __init__(self, workers: int) -> None:
        self.workers = workers
        self._executor: ThreadPoolExecutor | None = None

    async def start(self) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=self.workers, thread_name_prefix="lumora-worker"
        )
        asyncio.get_running_loop().set_default_executor(self._executor)

    async def stop(self) -> None:
        executor = self._executor
        self._executor = None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=False)

    def health(self) -> ServiceHealth:
        alive = self._executor is not None
        return ServiceHealth(
            self.name, alive, alive, f"{self.workers} worker(s)" if alive else "stopped"
        )


class _IndexRecoveryAdapter:
    name = "index-recovery"

    def __init__(
        self, repository: CaptureRepository, paths: DataPaths, config: StartupConfig
    ) -> None:
        self.repository = repository
        self.paths = paths
        self.config = config
        self.recovered = False
        self.error: str | None = None

    async def start(self) -> None:
        try:
            await self.repository.rebuild(
                self.paths.captures, additional_roots=self.paths.additional_capture_roots
            )
            if self.repository.rebuild_errors:
                self.error = (
                    f"skipped {len(self.repository.rebuild_errors)} invalid capture package(s)"
                )
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            raise
        self.recovered = True

    async def stop(self) -> None:
        return None

    def health(self) -> ServiceHealth:
        return ServiceHealth(
            self.name,
            self.recovered,
            True,
            self.error or (None if self.recovered else "recovery pending"),
        )


class _SQLiteResourceStore:
    """Async read adapter for rebuildable index projections."""

    _queries: ClassVar[dict[str, tuple[str, tuple[str, ...]]]] = {
        "studies": ("SELECT * FROM studies ORDER BY study_uid", ("study_uid",)),
        "series": (
            "SELECT * FROM series ORDER BY study_uid, series_uid",
            ("study_uid", "series_uid"),
        ),
        "instances": ("SELECT * FROM instances ORDER BY instance_id", ("instance_id",)),
        "events": (
            "SELECT * FROM event_window ORDER BY capture_id, sequence",
            ("capture_id", "sequence"),
        ),
    }
    _lookup_keys: ClassVar[dict[str, str]] = {
        "studies": "study_uid",
        "series": "series_uid",
        "instances": "instance_id",
        "events": "event_id",
    }

    def __init__(self, storage: StorageDatabases) -> None:
        self.storage = storage

    async def list(self, resource: str) -> tuple[Mapping[str, Any], ...]:
        query = self._queries.get(resource)
        if query is None:
            return ()
        rows = await self.storage.index.execute_read(query[0])
        return tuple(_row_mapping(resource, row) for row in rows)

    async def list_page(
        self,
        resource: str = "captures",
        *,
        offset: int,
        limit: int,
        sort: str | None = None,
        filter: str | None = None,
    ) -> tuple[tuple[Mapping[str, Any], ...], int]:
        query = self._queries.get(resource)
        if query is None or offset < 0 or limit < 1:
            return (), 0
        table = resource if resource != "events" else "event_window"
        allowed = {
            "studies": {
                "study_uid": "study_uid",
                "first_seen_at": "first_seen_at",
                "last_seen_at": "last_seen_at",
                "instance_count": "instance_count",
            },
            "series": {
                "study_uid": "study_uid",
                "series_uid": "series_uid",
                "first_seen_at": "first_seen_at",
                "last_seen_at": "last_seen_at",
                "instance_count": "instance_count",
            },
            "instances": {
                "instance_id": "instance_id",
                "study_uid": "study_uid",
                "series_uid": "series_uid",
                "sop_instance_uid": "sop_instance_uid",
                "created_at": "created_at",
                "capture_id": "capture_id",
            },
            "events": {
                "capture_id": "capture_id",
                "sequence": "sequence",
                "event_id": "event_id",
                "observed_at": "observed_at",
            },
        }.get(resource, {})
        clauses: list[str] = []
        parameters: list[object] = []
        if filter:
            field, separator, expected = filter.partition(":")
            if separator:
                column = allowed.get(field)
                if column is None:
                    raise ValueError(f"unsupported {resource} filter: {field}")
                clauses.append(f"LOWER(CAST({column} AS TEXT)) = LOWER(?)")
                parameters.append(expected)
            else:
                columns = tuple(dict.fromkeys(allowed.values()))
                if not columns:
                    return (), 0
                clauses.append(
                    " OR ".join(
                        f"LOWER(CAST({column} AS TEXT)) LIKE LOWER(?)" for column in columns
                    )
                )
                parameters.extend([f"%{filter}%"] * len(columns))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        default_order = query[0].split(" ORDER BY ", 1)[1]
        order: list[str] = []
        for raw in (sort or default_order).split(","):
            descending = raw.startswith("-")
            name = raw.lstrip("+-")
            column = allowed.get(name)
            if column is None:
                raise ValueError(f"unsupported {resource} sort: {name}")
            order.append(f"{column} {'DESC' if descending else 'ASC'}")
        requested = {raw.lstrip("+-") for raw in (sort or default_order).split(",")}
        for tie in query[1]:
            if tie not in requested and tie in allowed:
                order.append(f"{allowed[tie]} ASC")
        rows = await self.storage.index.execute_read(
            f"SELECT COUNT(*) AS total FROM {table}{where}", parameters
        )
        total = int(rows[0]["total"]) if rows else 0
        page_rows = await self.storage.index.execute_read(
            f"SELECT * FROM {table}{where} ORDER BY {', '.join(order)} LIMIT ? OFFSET ?",
            (*parameters, limit, offset),
        )
        return tuple(_row_mapping(resource, row) for row in page_rows), total

    async def get(self, resource: str, resource_id: str) -> Mapping[str, Any] | None:
        query = self._queries.get(resource)
        if query is None:
            return None
        rows = await self.storage.index.execute_read(
            f"{query[0].split(' ORDER BY ', 1)[0]} WHERE {self._lookup_keys[resource]} = ? LIMIT 1",
            (resource_id,),
        )
        return _row_mapping(resource, rows[0]) if rows else None

    async def delete(self, resource: str, resource_id: str) -> bool:
        return False


class _CaptureResourceStore(_SQLiteResourceStore):
    def __init__(self, repository: CaptureRepository, paths: DataPaths) -> None:
        super().__init__(repository.databases)
        self.repository = repository
        self.paths = paths

    async def list(self, resource: str) -> tuple[Mapping[str, Any], ...]:
        if resource != "captures":
            return await super().list(resource)
        records = await self.repository.list_captures()
        return tuple(_capture_mapping(record) for record in records)

    async def list_page(
        self,
        resource: str = "captures",
        *,
        offset: int,
        limit: int,
        sort: str | None = None,
        filter: str | None = None,
    ) -> tuple[tuple[Mapping[str, Any], ...], int]:
        if resource != "captures":
            return await super().list_page(
                resource, offset=offset, limit=limit, sort=sort, filter=filter
            )
        records, total = await self.repository.list_captures_page(
            offset=offset, limit=limit, sort=sort, filter=filter
        )
        return tuple(_capture_mapping(record) for record in records), total

    async def get(self, resource: str, resource_id: str) -> Mapping[str, Any] | None:
        if resource == "captures":
            record = await self.repository.get_capture(resource_id)
            return _capture_mapping(record) if record is not None else None
        return await super().get(resource, resource_id)

    async def delete(self, resource: str, resource_id: str) -> bool:
        record = await self.get(resource, resource_id)
        if record is None or resource != "captures":
            return False
        path = Path(str(record["path"])).resolve()
        roots = tuple(root.resolve() for root in self.paths.allowed_capture_roots())
        if not any(path.parent == root for root in roots):
            raise ValueError("capture is outside a configured capture root")
        import shutil

        shutil.rmtree(path)
        await self.repository.remove_index_entry(resource_id)
        return True


def _json_value(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Mapping):
        values: dict[Any, Any] = dict(cast(Mapping[Any, Any], value))
        return {key: _json_value(item) for key, item in values.items()}
    if isinstance(value, (tuple, list)):
        items: tuple[Any, ...] = tuple(cast(Sequence[Any], value))
        return [_json_value(item) for item in items]
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if callable(isoformat) else value


def _row_mapping(resource: str, row: Any) -> Mapping[str, Any]:
    values = dict(row)
    if resource == "events":
        values["occurred_at"] = values.pop("observed_at", None)
    return values


def _capture_mapping(record: Any) -> Mapping[str, Any]:
    return {
        "capture_id": record.capture_id,
        "path": record.path,
        "source_root": record.source_root,
        "format_version": record.format_version,
        "created_at": record.created_at.isoformat(),
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
        "state": record.state,
        "fidelity": record.fidelity,
        "partial": record.partial,
        "promoted_from_buffer": record.promoted_from_buffer,
        "interruption_reason": record.interruption_reason,
        "manifest_sha256": record.manifest_sha256,
        "indexed_at": record.indexed_at.isoformat(),
        "objects": [
            item.__dict__
            if hasattr(item, "__dict__")
            else {
                "digest": item.digest,
                "study_uid": item.study_uid,
                "series_uid": item.series_uid,
                "sop_instance_uid": item.sop_instance_uid,
                "size": item.size,
            }
            for item in record.objects
        ],
    }


class _AuditProvider:
    def __init__(self, audit: AuditLog) -> None:
        self.audit = audit

    async def list(self, *, category: str | None = None, limit: int = 100) -> tuple[Any, ...]:
        return await self.audit.list(category=category, limit=limit)


class _BookmarkProvider:
    def __init__(self, repository: BookmarkRepository) -> None:
        self.repository = repository

    async def add_bookmark(
        self,
        name: str,
        study_uid: str,
        series_uid: str | None = None,
        capture_id: str | None = None,
        sop_instance_uid: str | None = None,
    ) -> Any:
        return await self.repository.add_bookmark(
            name, study_uid, series_uid, capture_id, sop_instance_uid
        )

    async def list_bookmarks(self, capture_id: str | None = None) -> Any:
        return await self.repository.list_bookmarks(capture_id)

    async def remove_bookmark(self, bookmark_id: str) -> bool:
        return await self.repository.remove_bookmark(bookmark_id)


class _StudyBrowserProvider:
    def __init__(self, repository: StudyProjectionRepository) -> None:
        self.repository = repository

    async def get_study_browser(self, study_uid: str) -> Mapping[str, Any] | None:
        studies = tuple(
            item for item in await self.repository.list_studies() if item.study_uid == study_uid
        )
        if not studies:
            return None
        series = await self.repository.list_series(study_uid)
        instances = await self.repository.list_instances(study_uid=study_uid)
        return {
            "study": _json_value(studies[0]),
            "series": [_json_value(item) for item in series],
            "instances": [_json_value(item) for item in instances],
        }


class _LiveEvidenceStore:
    """Expose indexed and rolling observed events through web read contracts."""

    def __init__(self, storage: StorageDatabases, ring_buffer: Any) -> None:
        self.storage = storage
        self.ring_buffer = ring_buffer

    async def list(self, resource: str) -> tuple[Mapping[str, Any], ...]:
        if resource == "events":
            indexed = await self.storage.index.execute_read(
                "SELECT raw_json FROM event_window ORDER BY capture_id, sequence"
            )
            values = [_event_mapping(json.loads(row["raw_json"])) for row in indexed]
            seen = {str(item.get("event_id")) for item in values}
            for record in self.ring_buffer.snapshot():
                if record.kind != "event":
                    continue
                try:
                    event = json.loads(record.raw)
                except (TypeError, ValueError):
                    continue
                event_id = str(event.get("event_id", ""))
                if event_id and event_id not in seen:
                    values.append(_event_mapping(event))
                    seen.add(event_id)
            values.sort(
                key=lambda item: (int(item.get("sequence") or 0), str(item.get("event_id")))
            )
            return tuple(values)
        if resource == "associations":
            events = await self.list("events")
            by_id: dict[str, dict[str, Any]] = {}
            for event in events:
                if event.get("aggregate_type") != "Association":
                    continue
                association_id = str(event.get("aggregate_id", ""))
                if not association_id:
                    continue
                row = by_id.setdefault(
                    association_id,
                    {
                        "association_id": association_id,
                        "status": "unknown",
                        "started_at": event.get("occurred_at"),
                        "completed_at": None,
                        "calling_ae": event.get("payload", {}).get("calling_ae"),
                        "called_ae": event.get("payload", {}).get("called_ae"),
                    },
                )
                phase = str(event.get("event_name", ""))
                row["status"] = phase.removeprefix("Association").lower() or row["status"]
                if phase in {"AssociationReleased", "AssociationAborted", "AssociationRejected"}:
                    row["completed_at"] = event.get("occurred_at")
            return tuple(by_id.values())
        return ()

    async def list_page(
        self,
        resource: str,
        *,
        offset: int,
        limit: int,
        sort: str | None = None,
        filter: str | None = None,
    ) -> tuple[tuple[Mapping[str, Any], ...], int]:
        if resource == "events":
            return await self.list_events_page(
                EventPageQuery(
                    offset=offset,
                    limit=limit,
                    sort=sort,
                    filter=filter,
                    correlation_id=None,
                    sequence=None,
                    sequence_from=None,
                    sequence_to=None,
                    occurred_from=None,
                    occurred_to=None,
                )
            )
        if resource == "associations":
            return await self.list_associations_page(
                offset=offset, limit=limit, sort=sort, filter=filter
            )
        values = list(await self.list(resource))
        if sort:
            for raw in reversed(sort.split(",")):
                descending = raw.startswith("-")
                field = raw.lstrip("+-")
                values.sort(
                    key=lambda item, name=field: (item.get(name) is None, str(item.get(name, ""))),
                    reverse=descending,
                )
        total = len(values)
        return tuple(values[offset : offset + limit]), total

    async def list_events_page(
        self, query: EventPageQuery
    ) -> tuple[tuple[Mapping[str, Any], ...], int]:
        """Page indexed events in SQLite without materializing the standing collection."""
        allowed = {
            "capture_id": "capture_id",
            "event_id": "json_extract(raw_json, '$.event_id')",
            "event_name": "json_extract(raw_json, '$.event_name')",
            "correlation_id": "json_extract(raw_json, '$.correlation_id')",
            "aggregate_id": "json_extract(raw_json, '$.aggregate_id')",
            "origin": "json_extract(raw_json, '$.origin')",
            "sequence": "sequence",
            "occurred_at": "COALESCE(json_extract(raw_json, '$.occurred_at'), observed_at)",
            "severity": "json_extract(raw_json, '$.severity')",
        }
        clauses: list[str] = []
        parameters: list[object] = []
        if query.correlation_id is not None:
            clauses.append(f"{allowed['correlation_id']} = ?")
            parameters.append(query.correlation_id)
        if query.sequence is not None:
            clauses.append("sequence = ?")
            parameters.append(query.sequence)
        if query.sequence_from is not None:
            clauses.append("sequence >= ?")
            parameters.append(query.sequence_from)
        if query.sequence_to is not None:
            clauses.append("sequence <= ?")
            parameters.append(query.sequence_to)
        if query.occurred_from is not None:
            clauses.append(f"{allowed['occurred_at']} >= ?")
            parameters.append(query.occurred_from)
        if query.occurred_to is not None:
            clauses.append(f"{allowed['occurred_at']} <= ?")
            parameters.append(query.occurred_to)
        if query.filter:
            field, separator, expected = query.filter.partition(":")
            if separator:
                clauses.append(f"LOWER(CAST({allowed[field]} AS TEXT)) = LOWER(?)")
                parameters.append(expected)
            else:
                searchable = tuple(
                    allowed[name]
                    for name in (
                        "event_id",
                        "event_name",
                        "correlation_id",
                        "aggregate_id",
                        "origin",
                    )
                )
                clauses.append(
                    " OR ".join(
                        f"LOWER(CAST({column} AS TEXT)) LIKE LOWER(?)" for column in searchable
                    )
                )
                parameters.extend([f"%{query.filter}%"] * len(searchable))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        order: list[str] = []
        for raw in (query.sort or "capture_id,sequence").split(","):
            descending = raw.startswith("-")
            field = raw.lstrip("+-")
            order.append(f"{allowed[field]} {'DESC' if descending else 'ASC'}")
        requested = {raw.lstrip("+-") for raw in (query.sort or "capture_id,sequence").split(",")}
        for field in ("capture_id", "sequence"):
            if field not in requested:
                order.append(f"{field} ASC")

        count_rows = await self.storage.index.execute_read(
            f"SELECT COUNT(*) AS total FROM event_window{where}", parameters
        )
        total = int(count_rows[0]["total"]) if count_rows else 0
        rows = await self.storage.index.execute_read(
            "SELECT raw_json, observed_at FROM event_window"
            f"{where} ORDER BY {', '.join(order)} LIMIT ? OFFSET ?",
            (*parameters, query.limit, query.offset),
        )
        return tuple(_event_mapping(json.loads(row["raw_json"])) for row in rows), total

    async def list_associations_page(
        self,
        *,
        offset: int,
        limit: int,
        sort: str | None = None,
        filter: str | None = None,
    ) -> tuple[tuple[Mapping[str, Any], ...], int]:
        """Aggregate association evidence in SQL before applying page bounds."""
        base = """
            WITH ranked AS (
                SELECT
                    json_extract(raw_json, '$.aggregate_id') AS association_id,
                    json_extract(raw_json, '$.event_name') AS event_name,
                    COALESCE(json_extract(raw_json, '$.occurred_at'), observed_at) AS occurred_at,
                    json_extract(raw_json, '$.payload.calling_ae') AS calling_ae,
                    json_extract(raw_json, '$.payload.called_ae') AS called_ae,
                    sequence,
                    ROW_NUMBER() OVER (
                        PARTITION BY json_extract(raw_json, '$.aggregate_id')
                        ORDER BY sequence DESC
                    ) AS latest
                FROM event_window
                WHERE json_extract(raw_json, '$.aggregate_type') = 'Association'
            ), grouped AS (
                SELECT
                    association_id,
                    CASE
                        WHEN MAX(CASE WHEN latest = 1 THEN event_name END) = 'AssociationReleased'
                            THEN 'released'
                        WHEN MAX(CASE WHEN latest = 1 THEN event_name END) = 'AssociationAborted'
                            THEN 'aborted'
                        WHEN MAX(CASE WHEN latest = 1 THEN event_name END) = 'AssociationRejected'
                            THEN 'rejected'
                        WHEN MAX(CASE WHEN latest = 1 THEN event_name END) IS NOT NULL
                            THEN lower(substr(MAX(CASE WHEN latest = 1 THEN event_name END), 12))
                        ELSE 'unknown'
                    END AS status,
                    MIN(occurred_at) AS started_at,
                    MAX(CASE WHEN event_name IN
                        ('AssociationReleased', 'AssociationAborted', 'AssociationRejected')
                        THEN occurred_at END) AS completed_at,
                    MAX(calling_ae) AS calling_ae,
                    MAX(called_ae) AS called_ae
                FROM ranked
                GROUP BY association_id
            )
        """
        allowed = {
            "association_id": "association_id",
            "status": "status",
            "started_at": "started_at",
            "completed_at": "completed_at",
            "calling_ae": "calling_ae",
            "called_ae": "called_ae",
        }
        clauses: list[str] = []
        parameters: list[object] = []
        if filter:
            field, separator, expected = filter.partition(":")
            if separator:
                clauses.append(f"LOWER(CAST({allowed[field]} AS TEXT)) = LOWER(?)")
                parameters.append(expected)
            else:
                clauses.append(
                    " OR ".join(
                        f"LOWER(CAST({column} AS TEXT)) LIKE LOWER(?)"
                        for column in allowed.values()
                    )
                )
                parameters.extend([f"%{filter}%"] * len(allowed))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        order: list[str] = []
        for raw in (sort or "association_id").split(","):
            descending = raw.startswith("-")
            field = raw.lstrip("+-")
            order.append(f"{allowed[field]} {'DESC' if descending else 'ASC'}")
        if "association_id" not in {
            raw.lstrip("+-") for raw in (sort or "association_id").split(",")
        }:
            order.append("association_id ASC")
        count_rows = await self.storage.index.execute_read(
            f"{base} SELECT COUNT(*) AS total FROM grouped{where}", parameters
        )
        total = int(count_rows[0]["total"]) if count_rows else 0
        rows = await self.storage.index.execute_read(
            f"{base} SELECT * FROM grouped{where} ORDER BY {', '.join(order)} LIMIT ? OFFSET ?",
            (*parameters, limit, offset),
        )
        return tuple(dict(row) for row in rows), total

    async def get(self, resource: str, resource_id: str) -> Mapping[str, Any] | None:
        if resource == "events":
            rows = await self.storage.index.execute_read(
                "SELECT raw_json FROM event_window "
                "WHERE json_extract(raw_json, '$.event_id') = ? LIMIT 1",
                (resource_id,),
            )
            return _event_mapping(json.loads(rows[0]["raw_json"])) if rows else None
        if resource == "associations":
            records, _total = await self.list_associations_page(
                offset=0, limit=1, filter=f"association_id:{resource_id}"
            )
            return records[0] if records else None
        return None

    async def delete(self, resource: str, resource_id: str) -> bool:
        return False

    async def query_events(
        self, *, correlation_id: str | None = None, aggregate_id: str | None = None
    ) -> tuple[EventEnvelope, ...]:
        result: list[EventEnvelope] = []
        for value in await self.list("events"):
            if correlation_id is not None and value.get("correlation_id") != correlation_id:
                continue
            if aggregate_id is not None and value.get("aggregate_id") != aggregate_id:
                continue
            try:
                result.append(EventEnvelope.model_validate(value))
            except ValueError:
                continue
        return tuple(result)

    async def list_legs(self, association_id: str) -> tuple[Mapping[str, Any], ...]:
        events = await self.query_events(correlation_id=association_id)
        return tuple(
            {
                "leg_id": association_id,
                "association_id": association_id,
                "status": "observed",
            }
            for _ in ({"association_id": association_id},)
            if events
        )


class _FrameProvider:
    def __init__(self, sources: FileSystemInstanceSourceRepository, decoder: DecodeService) -> None:
        self.sources = sources
        self.decoder = decoder

    async def get_frame(self, instance_id: str, frame_number: int) -> Any:
        source = await self.sources.get_instance_source(instance_id)
        if source is None:
            return None
        try:
            return await self.decoder.decode(source, frame_number=frame_number)
        except DecodeError as error:
            return error.failure


class _MetadataProvider:
    def __init__(
        self, sources: FileSystemInstanceSourceRepository, inspector: MetadataInspectorService
    ) -> None:
        self.sources = sources
        self.inspector = inspector

    async def get_metadata(
        self, instance_id: str, *, include_private: bool = False, query: str | None = None
    ) -> Any:
        source = await self.sources.get_instance_source(instance_id)
        if source is None:
            return None
        return await self.inspector.inspect(source, include_private=include_private, query=query)


class _JobLifecycle:
    name = "operation-jobs"

    def __init__(self, jobs: InMemoryJobRegistry) -> None:
        self.jobs = jobs

    async def start(self) -> None:
        await self.jobs.startup_sweep(reason="process startup recovery")

    async def stop_accepting(self) -> None:
        return None

    async def drain(self) -> None:
        await self.jobs.shutdown(reason="lifecycle shutdown")

    async def stop(self) -> None:
        return None

    def health(self) -> ServiceHealth:
        return ServiceHealth(self.name, True, True, None)


def _event_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return dict(value)


class _EventBusAdapter:
    name = "event-bus"

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus

    async def start(self) -> None:
        await self.bus.start()

    async def stop(self) -> None:
        await self.bus.stop()

    def health(self) -> ServiceHealth:
        return ServiceHealth(
            self.name, self.bus.started, self.bus.started, None if self.bus.started else "stopped"
        )


def _not_started_alive(health: ServiceHealth) -> ServiceHealth:
    return ServiceHealth(health.name, health.ready, True, health.detail)


def _listener_health(listener: DICOMListener) -> ServiceHealth:
    detail = (
        f"{listener.config.bind_host}:{listener.config.port}; "
        f"accepted={listener.accepted_associations}; ingress_failures={listener.ingress_failures}"
        if listener.started
        else "listener stopped"
    )
    return ServiceHealth(listener.name, listener.started, listener.started, detail)


def _default_allowed_hosts(config: StartupConfig) -> tuple[str, ...]:
    hosts = {"localhost", "127.0.0.1", "[::1]"}
    if config.bind_host not in {"0.0.0.0", "::"}:
        hosts.add(config.bind_host)
    return tuple(sorted(hosts))


def build_production_runtime(config: StartupConfig) -> ProductionRuntime:
    """Create the fully composed app using the canonical data root and production services."""
    paths = DataPaths.from_config(config)
    paths.initialise()
    clock = SystemClock()
    storage = StorageDatabases.from_paths(paths)
    storage.app.initialise()
    storage.index.initialise()
    audit = AuditLog(storage.app)
    bus = EventBus(clock=clock)
    lifecycle = LifecycleManager(shutdown_grace_seconds=config.shutdown_grace_seconds)
    capture_repository = CaptureRepository(storage, clock=clock)
    recovery = _IndexRecoveryAdapter(capture_repository, paths, config)
    capture_engine = CaptureEngine(
        paths.captures,
        ring_root=paths.ringbuffer,
        event_ingress=bus,
        capture_repository=capture_repository,
        clock=clock,
        id_generator=bus.id_generator,
    )
    lifecycle.register(_EventBusAdapter(bus))
    executor = _DefaultExecutorAdapter(config.executor_workers)
    lifecycle.register(executor)
    lifecycle.register(recovery)
    lifecycle.register(_CaptureEngineAdapter(capture_engine, event_bus=bus))
    dicom_listener = DICOMListener(
        DICOMListenerConfig(bind_host=config.dicom_bind_host, port=config.dicom_port),
        event_ingress=bus,
        c_store_sink=capture_engine.store_c_store,
        pdu_trace_sink=cast(Any, capture_engine),
        clock=clock,
        id_generator=bus.id_generator,
    )
    lifecycle.register(dicom_listener)
    metrics = MetricRegistry()
    alerts = AlertRegistry(metrics, _thresholds(config))
    health = HealthRegistry()
    plugin_repo = PluginRepository(paths.plugins)
    study_repository = StudyProjectionRepository(
        storage, capture_roots=paths.allowed_capture_roots(), clock=clock
    )
    bookmark_repository = BookmarkRepository(storage, clock=clock, id_generator=bus.id_generator)
    operation_registry = SQLiteOperationRegistry(storage)
    settings_store = RuntimeSettingsStore(
        paths.settings_file, event_publisher=bus, clock=clock, id_generator=bus.id_generator
    )
    settings_store.load()
    dicom_listener.update_allowed_calling_aets(frozenset(settings_store.settings.ae_allowlist))
    dicom_listener.update_allowed_source_ips(frozenset(settings_store.settings.ip_allowlist))
    capture_engine.ring_buffer.update_config(
        retention_seconds=float(settings_store.settings.ring_buffer_seconds),
        max_bytes=settings_store.settings.ring_buffer_max_mb * 1024 * 1024,
        events_only=settings_store.settings.ring_buffer_events_only,
    )
    security_policy = SecurityPolicy(
        read_only=config.read_only or settings_store.settings.read_only,
        allowed_hosts=config.allowed_hosts or _default_allowed_hosts(config),
        allowed_origins=config.allowed_origins,
        trusted_proxies=config.trusted_proxies,
    )
    source_repository = FileSystemInstanceSourceRepository(
        paths.captures, storage, capture_roots=paths.allowed_capture_roots()
    )
    decode_cache = LRUFrameCache(
        max_bytes=settings_store.settings.decode_cache_max_mb * 1024 * 1024
    )
    decode_service = DecodeService(clock=clock, cache=decode_cache)
    metadata_inspector = MetadataInspectorService()
    frame_provider = _FrameProvider(source_repository, decode_service)
    metadata_provider = _MetadataProvider(source_repository, metadata_inspector)
    live_evidence = _LiveEvidenceStore(storage, capture_engine.ring_buffer)
    transfer_inspector = TransferInspectorService(live_evidence, live_evidence)
    job_registry = InMemoryJobRegistry(
        clock=clock,
        id_generator=bus.id_generator,
        durable=operation_registry,
        progress_publisher=bus,
    )
    job_lifecycle = _JobLifecycle(job_registry)
    lifecycle.register(job_lifecycle)
    report_service = ReportService(paths.captures)
    report_jobs = ReportJobService(
        report_service,
        cast(Any, job_registry),
        paths.reports,
        publisher=cast(Any, bus),
        clock=clock,
        id_generator=bus.id_generator,
    )
    summary_service = CaptureSummaryService(paths.captures)

    def diagnostic_sink(diagnostic: PluginDiagnostic) -> None:
        metrics.observe_plugin_diagnostic(diagnostic)
        log_operational(
            get_logger("lumora.plugins"),
            "plugin hook diagnostic",
            level="warning",
            plugin_id=diagnostic.plugin_id,
            hook=diagnostic.hook,
            diagnostic=diagnostic.event_name,
            diagnostic_message=diagnostic.message,
            elapsed_ns=diagnostic.elapsed_ns,
            budget_ns=diagnostic.budget_ns,
        )

    plugin_service = PluginService(
        plugin_repo,
        clock=clock,
        diagnostic_sink=diagnostic_sink,
        timing_sink=metrics.observe_plugin_timing,
    )
    plugin_provider = PluginServiceAdapter(
        plugin_service, audit=audit, clock=clock, metrics=metrics
    )
    for record in plugin_service.records():
        metrics.set_plugin_status(record.manifest.plugin_id, record.status.value)

    health.register(
        "event-bus",
        lambda: ServiceHealth("event-bus", bus.started, True, None if bus.started else "stopped"),
    )
    health.register("executor", lambda: _not_started_alive(executor.health()))
    health.register("index-recovery", recovery.health)
    health.register(
        "index-db",
        lambda: _database_health(
            "index-db", storage.index, ("schema_metadata", "captures", "event_window")
        ),
    )
    health.register("capture-engine", lambda: _not_started_alive(capture_engine.health()))
    health.register("dicom-listener", lambda: _not_started_alive(_listener_health(dicom_listener)))
    health.register(
        "app-db",
        lambda: _database_health("app-db", storage.app, ("schema_metadata", "jobs", "audit_log")),
    )
    health.register("plugin-host", lambda: _plugin_health(plugin_service))
    health.register("operation-jobs", job_lifecycle.health)

    # pyright: ignore[reportArgumentType]
    async def security_audit_sink(code: str, payload: Mapping[str, object]) -> None:  # pyright: ignore[reportArgumentType]
        await audit.append(
            AuditCategory.SECURITY_FAILURE,
            entity_type="http-request",
            occurred_at=clock.now(),
            payload={"code": code, **dict(payload)},
        )

    application = create_app(
        clock=clock,
        event_clock=clock,
        event_bus=cast(LiveEventSource, bus),
        event_publisher=cast(Any, bus),
        capture_engine=capture_engine,
        retention_provider=_CaptureRetentionProvider(capture_engine),
        capture_store=_CaptureResourceStore(capture_repository, paths),
        projection_store=_SQLiteResourceStore(storage),
        association_store=live_evidence,
        event_store=live_evidence,
        operation_registry=operation_registry,
        audit_provider=_AuditProvider(audit),
        bookmark_provider=_BookmarkProvider(bookmark_repository),
        study_browser_provider=_StudyBrowserProvider(study_repository),
        frame_provider=frame_provider,
        metadata_provider=metadata_provider,
        reports_provider=summary_service,
        report_job_provider=report_jobs,
        transfer_inspector=transfer_inspector,
        lifecycle_manager=lifecycle,
        event_id_generator=bus.id_generator,
        health_provider=HealthRegistryAdapter(health),
        metrics_provider=metrics,
        alert_provider=alerts,
        security_audit_sink=security_audit_sink,
        settings_provider=AuditedSettingsProvider(
            settings_store,
            audit,
            clock,
            ring_buffer=capture_engine.ring_buffer,
            decode_cache=decode_cache,
            dicom_listener=dicom_listener,
            security_policy=security_policy,
            base_read_only=config.read_only,
        ),
        plugin_provider=plugin_provider,
        security_policy=security_policy,
    )
    application.state.config = config
    application.state.paths = paths
    application.state.storage = storage
    application.state.event_bus = bus
    application.state.lifecycle_manager = lifecycle
    application.state.health_registry = health
    application.state.metrics = metrics
    application.state.alerts = alerts
    application.state.audit_log = audit
    application.state.plugin_service = plugin_service
    application.state.plugin_provider = plugin_provider
    application.state.dicom_listener = dicom_listener
    application.state.job_registry = job_registry
    application.state.report_service = report_service
    application.state.report_job_service = report_jobs
    application.state.decode_service = decode_service
    application.state.settings_store = settings_store
    application.state.executor_workers = config.executor_workers
    return ProductionRuntime(
        app=application,
        lifecycle=lifecycle,
        capture_engine=capture_engine,
        dicom_listener=dicom_listener,
        bus=bus,
        paths=paths,
    )


def build_production_app(config: StartupConfig) -> FastAPI:
    """Create the fully composed app using the canonical data root and production services."""
    return build_production_runtime(config).app


def _database_health(name: str, database: Any, required_tables: tuple[str, ...]) -> ServiceHealth:
    path = database.path
    if not path.is_file():
        return ServiceHealth(name, False, True, f"missing database: {path}")
    try:
        with database.connection(read_only=True) as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ("
                + ",".join("?" for _ in required_tables)
                + ")",
                required_tables,
            ).fetchall()
        found = {str(row[0]) for row in rows}
    except Exception as exc:  # noqa: BLE001 - health must report, not crash
        return ServiceHealth(
            name, False, True, f"database probe failed: {type(exc).__name__}: {exc}"
        )
    missing = tuple(table for table in required_tables if table not in found)
    if missing:
        return ServiceHealth(name, False, True, f"missing tables: {', '.join(missing)}")
    return ServiceHealth(name, True, True, None)


def _plugin_health(service: PluginService) -> ServiceHealth:
    result = service.health()
    return ServiceHealth(result.name, result.ready, result.alive, result.detail)


def _thresholds(config: StartupConfig) -> AlertThresholds:
    return AlertThresholds(
        plugin_errors_warning=getattr(config, "plugin_errors_warning", 1),
        plugin_errors_critical=getattr(config, "plugin_errors_critical", 3),
        budget_breaches_warning=getattr(config, "budget_breaches_warning", 1),
        budget_breaches_critical=getattr(config, "budget_breaches_critical", 3),
        event_drops_warning=getattr(config, "event_drops_warning", 1),
        event_drops_critical=getattr(config, "event_drops_critical", 10),
    )


__all__ = [
    "HealthRegistryAdapter",
    "PluginServiceAdapter",
    "ProductionRuntime",
    "build_production_app",
    "build_production_runtime",
]
