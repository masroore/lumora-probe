# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Shared workspace command definitions."""

from __future__ import annotations

from dataclasses import dataclass

from .ui_navigation import UI_ROUTES, NavigationGroup


@dataclass(frozen=True, slots=True)
class UIAction:
    """Executable or explicitly unavailable browser command."""

    name: str
    label: str
    href: str | None
    shortcut: str | None = None
    unavailable_reason: str | None = None


UI_ACTIONS: tuple[UIAction, ...] = tuple(
    UIAction(f"navigate-{route.name}", f"Open {route.label}", route.path)
    for route in UI_ROUTES
    if route.navigable
) + (
    UIAction("toggle-explorer", "Toggle Explorer", None, "Ctrl+Shift+E"),
    UIAction("toggle-inspector", "Toggle Inspector", None, "Ctrl+Shift+I"),
)

PRIMARY_ACTIONS = tuple(
    action
    for route in UI_ROUTES
    if route.group is NavigationGroup.PRIMARY and route.navigable
    for action in UI_ACTIONS
    if action.name == f"navigate-{route.name}"
)

__all__ = ["PRIMARY_ACTIONS", "UI_ACTIONS", "UIAction"]
