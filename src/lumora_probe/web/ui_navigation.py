# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Canonical browser route and action definitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class NavigationGroup(StrEnum):
    """Workspace navigation placement."""

    PRIMARY = "primary"
    UTILITY = "utility"
    CONTEXTUAL = "contextual"


@dataclass(frozen=True, slots=True)
class UIRoute:
    """One canonical server-rendered workspace route."""

    name: str
    path: str
    label: str
    description: str
    group: NavigationGroup
    icon: str
    tabs: tuple[str, ...] = ()

    @property
    def parameter_names(self) -> tuple[str, ...]:
        return tuple(part[1:-1] for part in self.path.split("/") if part.startswith("{"))

    @property
    def navigable(self) -> bool:
        return not self.parameter_names


UI_ROUTES: tuple[UIRoute, ...] = (
    UIRoute(
        "dashboard", "/dashboard", "Dashboard", "Operational overview", NavigationGroup.PRIMARY, "◫"
    ),
    UIRoute(
        "live", "/live", "Live Monitor", "Current DICOM activity", NavigationGroup.PRIMARY, "◉"
    ),
    UIRoute(
        "captures", "/captures", "Captures", "Recorded investigations", NavigationGroup.PRIMARY, "▣"
    ),
    UIRoute(
        "capture-detail",
        "/captures/{capture_id}",
        "Capture",
        "Capture investigation",
        NavigationGroup.CONTEXTUAL,
        "▣",
        ("overview", "transfer", "analysis", "events", "report"),
    ),
    UIRoute(
        "studies", "/studies", "Studies", "Cross-capture projections", NavigationGroup.PRIMARY, "▤"
    ),
    UIRoute(
        "study-detail",
        "/studies/{study_uid}",
        "Study",
        "Study investigation",
        NavigationGroup.CONTEXTUAL,
        "▤",
        ("overview", "instances", "analysis", "events"),
    ),
    UIRoute(
        "instance-detail",
        "/instances/{instance_id}",
        "Instance",
        "Instance inspection",
        NavigationGroup.CONTEXTUAL,
        "▧",
        ("metadata", "properties", "transfer", "analysis", "events"),
    ),
    UIRoute(
        "search", "/search", "Search", "URL-owned workspace search", NavigationGroup.PRIMARY, "⌕"
    ),
    UIRoute(
        "replay", "/replay", "Replay", "Replay history and creation", NavigationGroup.PRIMARY, "↻"
    ),
    UIRoute(
        "replay-detail",
        "/replay/{operation_id}",
        "Replay operation",
        "Replay progress and result",
        NavigationGroup.CONTEXTUAL,
        "↻",
        ("configuration", "progress", "events", "result"),
    ),
    UIRoute(
        "settings", "/settings", "Settings", "Effective configuration", NavigationGroup.UTILITY, "⚙"
    ),
    UIRoute(
        "plugins", "/plugins", "Plugins", "Trusted plugin status", NavigationGroup.UTILITY, "◇"
    ),
    UIRoute(
        "plugin-detail",
        "/plugins/{plugin_id}",
        "Plugin",
        "Plugin inspection",
        NavigationGroup.CONTEXTUAL,
        "◇",
        ("manifest", "status", "metrics", "audit"),
    ),
    UIRoute("audit", "/audit", "Audit", "Immutable activity history", NavigationGroup.UTILITY, "≡"),
    UIRoute(
        "operation-detail",
        "/operations/{operation_id}",
        "Operation",
        "Background operation detail",
        NavigationGroup.CONTEXTUAL,
        "◷",
    ),
    UIRoute(
        "report-detail",
        "/reports/{operation_id}",
        "Report",
        "Report state and preview",
        NavigationGroup.CONTEXTUAL,
        "▰",
    ),
)

ROUTES_BY_NAME = {route.name: route for route in UI_ROUTES}


def routes_for(group: NavigationGroup) -> tuple[UIRoute, ...]:
    """Return ordered routes belonging to a navigation group."""

    return tuple(route for route in UI_ROUTES if route.group is group and route.navigable)


__all__ = ["ROUTES_BY_NAME", "UI_ROUTES", "NavigationGroup", "UIRoute", "routes_for"]
