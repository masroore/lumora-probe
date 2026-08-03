# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Capture-backed view models for the server-rendered investigation workspace."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import ceil
from typing import Any, Protocol, cast

from .resources import InMemoryResourceStore, ResourceStore


class StudyBrowserSource(Protocol):
    """Optional provenance-aware study projection source."""

    async def get_study_browser(self, study_uid: str) -> Mapping[str, Any] | None: ...


class InvestigationProvider(Protocol):
    """Read-only composition boundary used by HTML investigation routes."""

    async def context(
        self,
        route_name: str,
        *,
        params: Mapping[str, str],
        query: Mapping[str, str],
    ) -> Mapping[str, Any]: ...


class ResourceInvestigationProvider:
    """Compose existing public resource contracts into bounded UI view models."""

    def __init__(
        self,
        *,
        capture_store: ResourceStore | None = None,
        projection_store: ResourceStore | None = None,
        event_store: ResourceStore | None = None,
        study_browser: StudyBrowserSource | None = None,
        retention_map: Any | None = None,
        workspace_data: Mapping[str, Any] | None = None,
    ) -> None:
        self._captures = capture_store or InMemoryResourceStore()
        self._projections = projection_store or InMemoryResourceStore()
        self._events = event_store or InMemoryResourceStore()
        self._study_browser = study_browser
        self._retention_map = retention_map
        self._workspace_data = workspace_data or {}

    async def context(
        self,
        route_name: str,
        *,
        params: Mapping[str, str],
        query: Mapping[str, str],
    ) -> Mapping[str, Any]:
        if route_name == "captures":
            return await self._collection("captures", query, "/captures")
        if route_name == "capture-detail":
            return await self._capture_detail(params["capture_id"])
        if route_name == "studies":
            return await self._collection("studies", query, "/studies")
        if route_name == "study-detail":
            return await self._study_detail(params["study_uid"])
        if route_name == "instance-detail":
            return await self._instance_detail(params["instance_id"])
        if route_name == "search":
            return await self._search(query)
        return {}

    async def _collection(
        self, resource: str, query: Mapping[str, str], base_path: str
    ) -> Mapping[str, Any]:
        page = _positive_int(query.get("page"), 1)
        page_size = min(_positive_int(query.get("page_size"), 50), 100)
        sort = query.get("sort")
        filter_value = query.get("filter")
        items, total = await self._store_for(resource).list_page(
            resource,
            offset=(page - 1) * page_size,
            limit=page_size,
            sort=sort,
            filter=filter_value,
        )
        return {
            "items": tuple(_mapping(item) for item in items),
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": max(1, ceil(total / page_size)),
            "base_path": base_path,
            "sort": sort or "",
            "filter": filter_value or "",
        }

    async def _capture_detail(self, capture_id: str) -> Mapping[str, Any]:
        capture = await self._captures.get("captures", capture_id)
        if capture is None:
            return {"missing": True, "capture_id": capture_id}
        events = await self._events.list("events")
        capture_events = tuple(
            _mapping(event)
            for event in events
            if str(event.get("capture_id", event.get("payload", {}).get("capture_id", "")))
            == capture_id
        )
        objects = tuple(_mapping(item) for item in _sequence(capture.get("objects", ())))
        return {
            "capture": _mapping(capture),
            "events": tuple(
                sorted(capture_events, key=lambda item: _sequence_value(item, "sequence"))
            ),
            "objects": objects,
            "studies": _capture_studies(objects),
            "findings": tuple(self._workspace_data.get("findings", ())),
            "report_href": f"/captures/{capture_id}?tab=report",
        }

    async def _study_detail(self, study_uid: str) -> Mapping[str, Any]:
        browser: Mapping[str, Any] | None = None
        if self._study_browser is not None:
            browser = await self._study_browser.get_study_browser(study_uid)
        if browser is None:
            study = await self._projections.get("studies", study_uid)
            if study is None:
                return {"missing": True, "study_uid": study_uid}
            series = await self._projections.list("series")
            instances = await self._projections.list("instances")
            browser = {
                "study": study,
                "series": tuple(item for item in series if item.get("study_uid") == study_uid),
                "instances": tuple(
                    item for item in instances if item.get("study_uid") == study_uid
                ),
            }
        result = {key: value for key, value in browser.items()}
        result.setdefault("study_uid", study_uid)
        result["series"] = tuple(_mapping(item) for item in _sequence(result.get("series", ())))
        result["instances"] = tuple(
            _mapping(item) for item in _sequence(result.get("instances", ()))
        )
        if self._retention_map is not None and hasattr(self._retention_map, "retention_by_digest"):
            retention_by_digest = self._retention_map.retention_by_digest()
            result["instances"] = tuple(
                _with_retention(instance, retention_by_digest) for instance in result["instances"]
            )
        result["partial"] = bool(result.get("partial", False))
        return result

    async def _instance_detail(self, instance_id: str) -> Mapping[str, Any]:
        instance = await self._projections.get("instances", instance_id)
        if instance is None:
            return {"missing": True, "instance_id": instance_id}
        result = _mapping(instance)
        result["viewer"] = {
            "instance_id": instance_id,
            "capture_id": result.get("capture_id"),
            "frame_count": max(1, _int_value(result.get("frame_count"), 1)),
            "rows": result.get("rows"),
            "columns": result.get("columns"),
        }
        return {"instance": result, "events": await self._instance_events(result)}

    async def _instance_events(self, instance: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
        instance_id = str(instance.get("instance_id", instance.get("sop_instance_uid", "")))
        events = await self._events.list("events")
        return tuple(
            _mapping(event)
            for event in events
            if instance_id
            and instance_id
            in {
                str(event.get("aggregate_id", "")),
                str(event.get("payload", {}).get("instance_id", "")),
            }
        )

    async def _search(self, query: Mapping[str, str]) -> Mapping[str, Any]:
        page = _positive_int(query.get("page"), 1)
        page_size = min(_positive_int(query.get("page_size"), 50), 100)
        needle = query.get("q", "").casefold().strip()
        allowed = frozenset({"studies", "series", "instances", "events", "logs"})
        selected = {
            value.strip().casefold()
            for value in query.get("kinds", "studies,series,instances,events,logs").split(",")
            if value.strip()
        }
        unknown = sorted(selected - allowed)
        if unknown:
            return {
                "items": (),
                "page": 1,
                "page_size": page_size,
                "total": 0,
                "pages": 1,
                "query": query.get("q", ""),
                "kinds": ",".join(sorted(selected)),
                "error": f"Unsupported search surfaces: {', '.join(unknown)}.",
            }
        if not selected:
            selected = allowed
        rows: list[dict[str, Any]] = []
        sources = (
            ("studies", self._projections),
            ("series", self._projections),
            ("instances", self._projections),
            ("events", self._events),
        )
        for kind, store in sources:
            if kind not in selected:
                continue
            items, _ = await store.list_page(kind, offset=0, limit=200)
            rows.extend(_search_rows(kind, items, needle))
        rows.sort(key=lambda item: (str(item["kind"]), str(item["label"]), str(item["id"])))
        total = len(rows)
        start = (page - 1) * page_size
        return {
            "items": tuple(rows[start : start + page_size]),
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": max(1, ceil(total / page_size)),
            "query": query.get("q", ""),
            "kinds": ",".join(sorted(selected)),
        }

    def _store_for(self, resource: str) -> ResourceStore:
        return self._captures if resource == "captures" else self._projections


def _capture_studies(objects: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    seen: set[str] = set()
    result: list[Mapping[str, Any]] = []
    for item in objects:
        study_uid = str(item.get("study_uid", ""))
        if study_uid and study_uid not in seen:
            seen.add(study_uid)
            result.append({"study_uid": study_uid, "capture_id": item.get("capture_id")})
    return tuple(result)


def _with_retention(
    instance: Mapping[str, Any], retention_by_digest: Mapping[str, Any]
) -> Mapping[str, Any]:
    digest = instance.get("object_digest")
    if not isinstance(digest, str) or digest not in retention_by_digest:
        digests = instance.get("object_digests", ())
        if isinstance(digests, Sequence) and not isinstance(digests, (str, bytes)):
            digest_values = cast(Sequence[Any], digests)
            digest = next(
                (
                    item
                    for item in digest_values
                    if isinstance(item, str) and item in retention_by_digest
                ),
                None,
            )
    if not isinstance(digest, str):
        return instance
    retention = retention_by_digest[digest]
    as_dict = getattr(retention, "as_dict", None)
    value = as_dict() if callable(as_dict) else retention
    updated = dict(instance)
    updated["retention"] = value
    return updated


def _search_rows(
    kind: str, records: Sequence[Mapping[str, Any]], needle: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        identifier = _identifier(kind, record)
        label = _label(kind, record)
        haystack = " ".join(
            str(value)
            for value in (
                kind,
                identifier,
                label,
                record.get("study_uid"),
                record.get("series_uid"),
                record.get("sop_instance_uid"),
                record.get("event_name"),
                record.get("correlation_id"),
            )
            if value is not None
        ).casefold()
        if needle and needle not in haystack:
            continue
        rows.append(
            {
                "id": identifier,
                "kind": kind,
                "label": label,
                "study_uid": record.get("study_uid"),
                "series_uid": record.get("series_uid"),
                "sop_instance_uid": record.get("sop_instance_uid"),
                "capture_id": record.get("capture_id"),
                "sequence": record.get("sequence"),
                "href": _search_href(kind, record, identifier),
            }
        )
    return rows


def _search_href(kind: str, record: Mapping[str, Any], identifier: str) -> str:
    if kind == "studies":
        return f"/studies/{record.get('study_uid', identifier)}"
    if kind == "instances":
        return f"/instances/{record.get('instance_id', identifier)}"
    if kind == "series":
        return f"/studies/{record.get('study_uid', '')}?tab=instances&series={record.get('series_uid', identifier)}"
    capture_id = record.get("capture_id")
    return f"/captures/{capture_id}?tab=events" if capture_id else "/search"


def _identifier(kind: str, record: Mapping[str, Any]) -> str:
    for field in {
        "studies": ("study_uid", "id"),
        "series": ("series_uid", "id"),
        "instances": ("instance_id", "sop_instance_uid", "id"),
        "events": ("event_id", "id"),
    }.get(kind, ("id",)):
        value = record.get(field)
        if value is not None and str(value):
            return str(value)
    return f"{kind}:unknown"


def _label(kind: str, record: Mapping[str, Any]) -> str:
    if kind == "series":
        return f"{record.get('study_uid')}/{record.get('series_uid')}"
    if kind == "events":
        return f"{record.get('event_name', 'event')}#{record.get('sequence', '-')}"
    return str(
        record.get(
            {"studies": "study_uid", "instances": "sop_instance_uid"}.get(kind, "id"),
            kind,
        )
    )


def _mapping(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        typed = cast(Mapping[str, Any], value)
        return {str(key): item for key, item in typed.items()}
    return {}


def _sequence(value: object) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return cast(Sequence[Any], value)
    return ()


def _sequence_value(item: Mapping[str, Any], field: str) -> int:
    return _int_value(item.get(field), 0)


def _int_value(value: object, default: int) -> int:
    return value if type(value) is int else default


def _positive_int(value: str | None, default: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except ValueError:
        return default
    return parsed if parsed > 0 else default


__all__ = ["InvestigationProvider", "ResourceInvestigationProvider"]
