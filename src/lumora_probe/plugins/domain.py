# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Plugin lifecycle state and validated discovery records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .contracts import PluginHookName


class PluginStatus(StrEnum):
    """Operational state of a discovered plugin."""

    DISABLED = "disabled"
    ENABLED = "enabled"
    LOADED = "loaded"
    INVALID = "invalid"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Validated plugin manifest metadata."""

    plugin_id: str
    name: str
    version: str
    author: str
    description: str
    capabilities: tuple[str, ...]
    sdk_min: int
    sdk_max: int
    entry_point: str
    hooks: tuple[PluginHookName, ...]
    path: Path

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", self.plugin_id):
            raise ValueError(
                "plugin_id must contain only lowercase ASCII segments separated by dots or hyphens"
            )
        for field_name in ("plugin_id", "name", "version", "author", "description", "entry_point"):
            value = getattr(self, field_name)
            if type(value) is not str or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if self.sdk_min < 1 or self.sdk_max < self.sdk_min:
            raise ValueError("SDK compatibility range is invalid")
        if not self.hooks:
            raise ValueError("a plugin must declare at least one hook")
        if len(set(self.hooks)) != len(self.hooks):
            raise ValueError("plugin hooks must be unique")

    def as_dict(self) -> dict[str, Any]:
        """Return the stable public inspection shape."""

        return {
            "id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "sdk": {"min_major": self.sdk_min, "max_major": self.sdk_max},
            "entry_point": self.entry_point,
            "hooks": [hook.value for hook in self.hooks],
        }


@dataclass(frozen=True, slots=True)
class PluginRecord:
    """Inspection record returned by discovery and management APIs."""

    manifest: PluginManifest
    status: PluginStatus
    failure_count: int = 0
    last_error: str | None = None
    last_elapsed_ns: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-compatible plugin inspection data."""

        state = self.health_state
        return {
            **self.manifest.as_dict(),
            "status": self.status.value,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
            "last_elapsed_ns": self.last_elapsed_ns,
            "trusted_code": True,
            "capabilities_enforced": False,
            "health": {
                "state": state,
                "ready": state in {"healthy", "disabled"},
                "alive": state != "unhealthy",
            },
        }

    @property
    def health_state(self) -> str:
        """Map plugin lifecycle metadata to an operator-facing health state."""
        if self.status is PluginStatus.FAILED:
            return "unhealthy"
        if self.failure_count > 0:
            return "degraded"
        if self.status is PluginStatus.DISABLED:
            return "disabled"
        if self.status in {PluginStatus.LOADED, PluginStatus.ENABLED}:
            return "healthy"
        return "unhealthy"


@dataclass(frozen=True, slots=True)
class PluginHealth:
    """Structural health result used by composition roots."""

    name: str
    ready: bool
    alive: bool
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class PluginPolicy:
    """Containment policy; budgets measure execution but cannot interrupt Python code."""

    max_failures: int = 3
    hook_budget_ns: int = 100_000_000

    def __post_init__(self) -> None:
        if self.max_failures < 1:
            raise ValueError("max_failures must be positive")
        if self.hook_budget_ns < 1:
            raise ValueError("hook_budget_ns must be positive")


__all__: tuple[str, ...] = ()
