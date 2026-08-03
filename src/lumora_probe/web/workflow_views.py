# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Server-rendered view models for Phase 24 controlled workflows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, cast


class WorkflowProvider(Protocol):
    """Read-side browser composition boundary for mutable workflows."""

    async def context(
        self,
        route_name: str,
        *,
        params: Mapping[str, str],
        query: Mapping[str, str],
    ) -> Mapping[str, Any]: ...


class EmptyWorkflowProvider:
    """Safe empty workflow view model used by isolated route tests."""

    async def context(
        self,
        route_name: str,
        *,
        params: Mapping[str, str],
        query: Mapping[str, str],
    ) -> Mapping[str, Any]:
        del params, query
        return {
            "route_name": route_name,
            "replays": (),
            "replay": None,
            "report": None,
            "settings": {"items": ()},
            "plugins": (),
            "plugin": None,
            "trust_notice": (
                "Enabled plugins are trusted in-process code. Manifest capabilities are "
                "disclosure only; capability enforcement is not provided."
            ),
        }


class RuntimeWorkflowProvider:
    """Compose bounded workflow facts from existing application providers."""

    def __init__(
        self,
        *,
        replay_provider: Any | None = None,
        operation_provider: Any | None = None,
        settings_provider: Any | None = None,
        plugin_provider: Any | None = None,
    ) -> None:
        self.replay_provider = replay_provider
        self.operation_provider = operation_provider
        self.settings_provider = settings_provider
        self.plugin_provider = plugin_provider

    async def context(
        self,
        route_name: str,
        *,
        params: Mapping[str, str],
        query: Mapping[str, str],
    ) -> Mapping[str, Any]:
        del query
        result: dict[str, Any] = {
            "route_name": route_name,
            "replays": (),
            "replay": None,
            "report": None,
            "settings": {"items": ()},
            "plugins": (),
            "plugin": None,
            "trust_notice": (
                "Enabled plugins are trusted in-process code and can do anything the Lumora "
                "process can. Manifest capabilities are disclosure only; enforcement is not provided."
            ),
        }
        if route_name == "replay" and self.replay_provider is not None:
            page = await self.replay_provider.list(limit=50)
            result["replays"] = tuple(page.get("items", ()))
        elif route_name == "replay-detail" and self.replay_provider is not None:
            result["replay"] = await self.replay_provider.get(params["operation_id"])
        elif route_name == "report-detail" and self.operation_provider is not None:
            operation = await self.operation_provider.get(params["operation_id"])
            if operation is not None and str(operation.get("job_type", "")) == "report-generation":
                parameters = operation.get("parameters")
                values = (
                    dict(cast(Mapping[str, Any], parameters))
                    if isinstance(parameters, Mapping)
                    else {}
                )
                result["report"] = {
                    "operation": operation,
                    "capture_id": values.get("capture_id"),
                    "format": values.get("format", "html"),
                    "rule_set_version": values.get("rule_set_version"),
                }
        elif route_name == "settings" and self.settings_provider is not None:
            settings = await self.settings_provider.get()
            raw_items = cast(Sequence[Any], settings.get("items", ()))
            result["settings"] = {
                **dict(settings),
                "items": tuple(
                    {
                        **dict(item),
                        "locked": item.get("source") in {"env", "file"},
                        "restart_required": item.get("name")
                        in {
                            "data_dir",
                            "captures_root",
                            "additional_capture_roots",
                            "bind_host",
                            "port",
                            "dicom_port",
                            "executor_workers",
                            "shutdown_grace_seconds",
                        },
                    }
                    for raw_item in raw_items
                    if isinstance(raw_item, Mapping)
                    for item in (cast(Mapping[str, Any], raw_item),)
                ),
            }
        elif route_name == "plugins" and self.plugin_provider is not None:
            result["plugins"] = tuple(self.plugin_provider.records())
        elif route_name == "plugin-detail" and self.plugin_provider is not None:
            try:
                result["plugin"] = self.plugin_provider.inspect(params["plugin_id"])
            except KeyError:
                result["plugin"] = None
        return result


__all__ = ["EmptyWorkflowProvider", "RuntimeWorkflowProvider", "WorkflowProvider"]
