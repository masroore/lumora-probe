"""Plugin inspection and restart-scoped enablement routes."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Mapping, Sequence
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException


class PluginProvider(Protocol):
    """Application-owned plugin management surface exposed to the web layer."""

    def records(self) -> Sequence[Mapping[str, Any]]: ...

    def inspect(self, plugin_id: str) -> Mapping[str, Any]: ...

    def set_enabled(
        self, plugin_id: str, enabled: bool
    ) -> Mapping[str, Any] | Awaitable[Mapping[str, Any]]: ...


class EmptyPluginProvider:
    """Safe default when application bootstrap has not configured plugin discovery."""

    def records(self) -> Sequence[Mapping[str, Any]]:
        return ()

    def inspect(self, plugin_id: str) -> Mapping[str, Any]:
        raise KeyError(plugin_id)

    def set_enabled(self, plugin_id: str, enabled: bool) -> Mapping[str, Any]:
        raise KeyError(plugin_id)


def create_plugin_router(provider: PluginProvider | None = None) -> APIRouter:
    """Create list/inspect/enable/disable routes; installation is intentionally absent."""

    active_provider = provider or EmptyPluginProvider()
    router = APIRouter(prefix="/plugins", tags=["plugins"])

    @router.get("")
    def list_plugins() -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return {
            "items": [dict(record) for record in active_provider.records()],
            "trust_notice": "Enabled plugins are trusted in-process code and can do anything the Lumora process can.",
            "capabilities_enforced": False,
        }

    @router.get("/{plugin_id}")
    def inspect_plugin(plugin_id: str) -> Mapping[str, Any]:  # pyright: ignore[reportUnusedFunction]
        try:
            return active_provider.inspect(plugin_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Plugin not found") from error

    @router.post("/{plugin_id}/enable")
    async def enable_plugin(plugin_id: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return await _set_enabled(active_provider, plugin_id, True)

    @router.post("/{plugin_id}/disable")
    async def disable_plugin(plugin_id: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return await _set_enabled(active_provider, plugin_id, False)

    return router


async def _set_enabled(provider: PluginProvider, plugin_id: str, enabled: bool) -> dict[str, Any]:
    try:
        result = provider.set_enabled(plugin_id, enabled)
        record = dict(await result if inspect.isawaitable(result) else result)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Plugin not found") from error
    return {"plugin": record, "restart_required": True}


__all__ = ["EmptyPluginProvider", "PluginProvider", "create_plugin_router"]
