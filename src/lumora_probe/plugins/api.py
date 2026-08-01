# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Public pluggy hook specifications and SDK entry points."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pluggy

from .contracts import (
    AnalysisContextDTO,
    CommandDTO,
    EventDTO,
    FindingDTO,
    ReportContextDTO,
    ReportContributionDTO,
    SettingDTO,
)

PLUGIN_PROJECT_NAME = "lumora_probe"
hookspec = pluggy.HookspecMarker(PLUGIN_PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PLUGIN_PROJECT_NAME)


class PluginHookSpecs:
    """Hook specifications implemented by trusted plugins."""

    @hookspec
    def on_event(self, event: EventDTO) -> None:
        """Observe one immutable event projection."""

    @hookspec
    def analyze(self, context: AnalysisContextDTO) -> Iterable[FindingDTO] | None:
        """Return deterministic findings for observed evidence."""

    @hookspec
    def contribute_report(
        self, context: ReportContextDTO
    ) -> Iterable[ReportContributionDTO] | None:
        """Return report sections for a generated report."""

    @hookspec
    def register_commands(self) -> Sequence[CommandDTO] | None:
        """Return command metadata; execution remains application-owned."""

    @hookspec
    def register_settings(self) -> Sequence[SettingDTO] | None:
        """Return setting metadata and defaults."""


def build_plugin_manager() -> pluggy.PluginManager:
    """Create a manager configured with the public SDK hook specifications."""

    manager = pluggy.PluginManager(PLUGIN_PROJECT_NAME)
    manager.add_hookspecs(PluginHookSpecs)
    return manager


__all__: tuple[str, ...] = ()
