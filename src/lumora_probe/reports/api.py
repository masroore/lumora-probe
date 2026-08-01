# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Public composition helpers for report generation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

from .contracts import ProgressCallback, RenderedReport, ReportFormat
from .service import ReportService


class ReportProvider:
    """Small application-facing facade for a report service."""

    def __init__(self, service: ReportService) -> None:
        self._service = service

    async def generate(
        self,
        capture_id: str,
        *,
        format: ReportFormat | str = ReportFormat.HTML,
        rule_set_version: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> RenderedReport | None:
        """Generate a report without coupling callers to repository details."""
        return await self._service.generate(
            capture_id,
            format=format,
            rule_set_version=rule_set_version,
            progress_callback=progress_callback,
        )


def create_report_provider(captures_root: Path) -> ReportProvider:
    """Create the default filesystem-backed report provider."""
    return ReportProvider(ReportService(captures_root))


async def generate_report(
    captures_root: Path,
    capture_id: str,
    *,
    format: ReportFormat | str = ReportFormat.HTML,
    rule_set_version: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> RenderedReport | None:
    """One-shot async helper for a background worker or CLI adapter."""
    return await ReportService(captures_root).generate(
        capture_id,
        format=format,
        rule_set_version=rule_set_version,
        progress_callback=progress_callback,
    )


# Protocol-like aliases retained for adapters that annotate callback signatures.
type ReportProgressCallback = Callable[[Mapping[str, Any]], Awaitable[None] | None]

__all__: tuple[str, ...] = ()
