# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Transport-neutral resource providers used by REST adapters."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol


class ResourceStore(Protocol):
    """Minimal async store contract exposed to the HTTP adapter."""

    async def list(self, resource: str) -> tuple[Mapping[str, Any], ...]: ...

    async def list_page(
        self,
        resource: str,
        *,
        offset: int,
        limit: int,
        sort: str | None = None,
        filter: str | None = None,
    ) -> tuple[tuple[Mapping[str, Any], ...], int]: ...

    async def get(self, resource: str, resource_id: str) -> Mapping[str, Any] | None: ...

    async def delete(self, resource: str, resource_id: str) -> bool: ...


class InMemoryResourceStore:
    """Small deterministic default store for app assembly and tests."""

    def __init__(
        self, resources: Mapping[str, Mapping[str, Mapping[str, Any]]] | None = None
    ) -> None:
        self._resources: dict[str, dict[str, dict[str, Any]]] = {
            resource: {key: dict(value) for key, value in values.items()}
            for resource, values in (resources or {}).items()
        }

    async def list(self, resource: str) -> tuple[Mapping[str, Any], ...]:
        values = self._resources.get(resource, {})
        return tuple(dict(value) for _, value in sorted(values.items()))

    async def list_page(
        self,
        resource: str,
        *,
        offset: int,
        limit: int,
        sort: str | None = None,
        filter: str | None = None,
    ) -> tuple[tuple[Mapping[str, Any], ...], int]:
        records = list(await self.list(resource))
        if filter:
            field, _, expected = filter.partition(":")
            if expected:
                records = [
                    item
                    for item in records
                    if str(item.get(field, "")).casefold() == expected.casefold()
                ]
            else:
                needle = filter.casefold()
                records = [item for item in records if needle in str(item).casefold()]
        if sort:
            for raw in reversed(sort.split(",")):
                descending = raw.startswith("-")
                field = raw.lstrip("+-")
                records.sort(
                    key=lambda item, name=field: (item.get(name) is None, str(item.get(name, ""))),
                    reverse=descending,
                )
        total = len(records)
        return tuple(records[offset : offset + limit]), total

    async def list_events_page(self, query: Any) -> tuple[tuple[Mapping[str, Any], ...], int]:
        """Serve the event-specific page contract without changing the test adapter shape."""
        from .event_routes import filter_events

        events = filter_events(tuple(await self.list("events")), query)
        from .query import QueryPolicy, apply_query

        policy = QueryPolicy.from_fields(
            sort_fields=("sequence", "occurred_at", "event_name", "severity"),
            filter_fields=("event_id", "event_name", "correlation_id", "aggregate_id", "origin"),
        )
        events = apply_query(
            events,
            policy=policy,
            value_for=lambda item, field: item.get(field),
            sort=query.sort,
            filter=query.filter,
        )
        total = len(events)
        return tuple(events[query.offset : query.offset + query.limit]), total

    async def get(self, resource: str, resource_id: str) -> Mapping[str, Any] | None:
        value = self._resources.get(resource, {}).get(resource_id)
        return dict(value) if value is not None else None

    async def delete(self, resource: str, resource_id: str) -> bool:
        values = self._resources.get(resource, {})
        return values.pop(resource_id, None) is not None

    def put(self, resource: str, resource_id: str, value: Mapping[str, Any]) -> None:
        self._resources.setdefault(resource, {})[resource_id] = dict(value)


class FilesystemCaptureStore(InMemoryResourceStore):
    """Capture store that removes the indexed capture directory on delete."""

    async def delete(self, resource: str, resource_id: str) -> bool:
        record = await self.get(resource, resource_id)
        if record is None:
            return False
        capture_path = record.get("path")
        if isinstance(capture_path, str):
            path = Path(capture_path).expanduser().resolve()
            if path.is_dir():
                shutil.rmtree(path)
        return await super().delete(resource, resource_id)


__all__: tuple[str, ...] = ()
