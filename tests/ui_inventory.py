# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Static interaction inventory for server-rendered workspace HTML."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Final


class InventoryError(AssertionError):
    """Rendered UI violates the interaction ownership contract."""


class _InventoryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.references: list[tuple[str, str]] = []
        self.controls: list[dict[str, str]] = []
        self.commands: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if identifier := values.get("id"):
            self.ids.append(identifier)
        for name in ("aria-controls", "aria-labelledby"):
            for reference in values.get(name, "").split():
                self.references.append((name, reference))
        if tag in {"button", "a", "input", "select", "textarea", "summary"}:
            self.controls.append({"tag": tag, **values})
        if command := values.get("data-command"):
            self.commands.add(command)


_OWNER_ATTRIBUTES: Final = {
    "data-command-palette",
    "data-panel-toggle",
    "data-tab",
    "data-copy-text",
    "data-copy-metadata-json",
    "data-copy-metadata-raw",
    "data-metadata-private",
    "data-promote-instance",
    "data-theme-select",
    "data-search-input",
    "data-dialog-close",
    "data-metadata-search",
    "data-palette-input",
    "data-viewer-previous",
    "data-viewer-frame",
    "data-viewer-next",
    "data-viewer-zoom-in",
    "data-viewer-zoom-out",
    "data-viewer-pan",
    "data-viewer-window-level",
    "data-viewer-invert",
    "data-viewer-reset",
    "data-viewer-cine",
    "data-viewer-fullscreen",
    "data-inspector-tab",
}


def validate_interactions(html: str, known_commands: set[str]) -> None:
    """Reject duplicate IDs, broken ARIA links, and unowned visible controls."""

    parser = _InventoryParser()
    parser.feed(html)
    duplicates = sorted(
        {identifier for identifier in parser.ids if parser.ids.count(identifier) > 1}
    )
    if duplicates:
        raise InventoryError(f"duplicate IDs: {duplicates}")
    identifiers = set(parser.ids)
    broken = sorted(
        f"{name}={target}" for name, target in parser.references if target not in identifiers
    )
    if broken:
        raise InventoryError(f"missing ARIA targets: {broken}")
    unresolved = parser.commands - known_commands
    if unresolved:
        raise InventoryError(f"unresolved commands: {sorted(unresolved)}")
    inert: list[str] = []
    for control in parser.controls:
        if "disabled" in control or control.get("aria-disabled") == "true":
            continue
        if control["tag"] == "a" and control.get("href"):
            continue
        if control["tag"] == "summary":
            continue
        if control.get("role") == "tab":
            continue
        if control["tag"] == "input" and control.get("type") in {"checkbox", "radio"}:
            continue
        if control["tag"] in {"input", "select", "textarea"} and (
            control.get("name") or any(attribute in control for attribute in _OWNER_ATTRIBUTES)
        ):
            continue
        if any(attribute in control for attribute in _OWNER_ATTRIBUTES):
            continue
        if control.get("type") in {"submit", "reset"}:
            continue
        if control["tag"] == "button" and control.get("type") == "button":
            inert.append(control.get("id") or control.get("aria-label") or "button")
            continue
        inert.append(control.get("id") or control.get("aria-label") or control["tag"])
    if inert:
        raise InventoryError(f"unowned visible controls: {inert}")


__all__ = ["InventoryError", "validate_interactions"]
