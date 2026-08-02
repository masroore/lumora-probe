# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Server-side UI view-model composition."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .ui_actions import UI_ACTIONS
from .ui_navigation import NavigationGroup, UIRoute, routes_for


@dataclass(frozen=True, slots=True)
class UIContext:
    """Immutable context shared by full-page and HTMX rendering."""

    route: UIRoute
    title: str
    active_tab: str | None
    route_params: Mapping[str, str]
    primary_routes: tuple[UIRoute, ...]
    utility_routes: tuple[UIRoute, ...]
    actions: tuple[Any, ...]


def build_ui_context(
    route: UIRoute, params: Mapping[str, str], requested_tab: str | None
) -> UIContext:
    """Validate URL-owned state and build shared navigation context."""

    active_tab = route.tabs[0] if route.tabs else None
    if requested_tab in route.tabs:
        active_tab = requested_tab
    suffix = next(iter(params.values()), "")
    title = f"{route.label} · {suffix}" if suffix else route.label
    return UIContext(
        route=route,
        title=title,
        active_tab=active_tab,
        route_params=MappingProxyType(dict(params)),
        primary_routes=routes_for(NavigationGroup.PRIMARY),
        utility_routes=routes_for(NavigationGroup.UTILITY),
        actions=UI_ACTIONS,
    )


__all__ = ["UIContext", "build_ui_context"]
