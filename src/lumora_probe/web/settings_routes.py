# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""REST routes for runtime settings with provenance."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Protocol, cast

from fastapi import APIRouter, Body

from lumora_probe.core.errors import SettingLockedError


class SettingsProvider(Protocol):
    """Read and update contract for the runtime settings store."""

    async def get(self) -> Mapping[str, Any]: ...

    async def update(self, values: Mapping[str, Any]) -> Mapping[str, Any]: ...


class InMemorySettingsProvider:
    """Small settings provider for app assembly and API tests."""

    def __init__(self, values: Mapping[str, Any] | None = None) -> None:
        self._values: dict[str, dict[str, Any]] = {
            key: dict(cast(Mapping[str, Any], value))
            for key, value in (values or {}).items()
            if isinstance(value, Mapping)
        }

    async def get(self) -> Mapping[str, Any]:
        return {"items": [dict(value) for value in self._values.values()]}

    async def update(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        for name, value in values.items():
            current = self._values.get(name)
            if isinstance(current, dict) and current.get("locked"):
                raise SettingLockedError(
                    code="LUMORA-SETTINGS-LOCKED-001",
                    message=f"Setting {name!r} is locked by a higher-precedence source.",
                    remediation="Change the setting in its owning startup or environment source.",
                    context={"setting": name, "source": current.get("source", "unknown")},
                )
            self._values[name] = {
                "name": name,
                "value": value,
                "source": "runtime",
                "locked": False,
            }
        return await self.get()


def create_settings_router(provider: SettingsProvider | None = None) -> APIRouter:
    """Create settings read/update routes."""

    settings_provider = provider or InMemorySettingsProvider()
    router = APIRouter(prefix="/settings", tags=["settings"])

    @router.get("")
    async def get_settings() -> Mapping[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return await settings_provider.get()

    @router.patch("")
    async def update_settings(  # pyright: ignore[reportUnusedFunction]
        values: Annotated[dict[str, Any], Body(...)],
    ) -> Mapping[str, Any]:
        return await settings_provider.update(values)

    return router


__all__: tuple[str, ...] = ()
