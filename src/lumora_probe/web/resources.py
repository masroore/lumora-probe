"""Transport-neutral resource providers used by REST adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class ResourceStore(Protocol):
    """Minimal async store contract exposed to the HTTP adapter."""

    async def list(self, resource: str) -> tuple[Mapping[str, Any], ...]: ...

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

    async def get(self, resource: str, resource_id: str) -> Mapping[str, Any] | None:
        value = self._resources.get(resource, {}).get(resource_id)
        return dict(value) if value is not None else None

    async def delete(self, resource: str, resource_id: str) -> bool:
        values = self._resources.get(resource, {})
        return values.pop(resource_id, None) is not None

    def put(self, resource: str, resource_id: str, value: Mapping[str, Any]) -> None:
        self._resources.setdefault(resource, {})[resource_id] = dict(value)


__all__: tuple[str, ...] = ()
