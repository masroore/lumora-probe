# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Plain-Python report aggregate and lifecycle."""

from __future__ import annotations

from enum import StrEnum

from lumora_probe.shared.errors import domain_invariant, invalid_transition


class ReportState(StrEnum):
    CREATED = "created"
    GENERATED = "generated"
    EXPORTED = "exported"
    ARCHIVED = "archived"


class Report:
    """An investigation artifact tied to a capture and rule-set version."""

    def __init__(
        self,
        report_id: str,
        capture_id: str,
        rule_set_version: str,
        *,
        format: str = "json",
    ) -> None:
        self.report_id = _identity(report_id, field="report_id")
        self.capture_id = _identity(capture_id, field="capture_id")
        self.rule_set_version = _identity(rule_set_version, field="rule_set_version")
        self.format = _identity(format, field="format")
        self.state = ReportState.CREATED

    @property
    def id(self) -> str:
        return self.report_id

    @property
    def status(self) -> ReportState:
        return self.state

    def generate(self) -> None:
        self._transition(ReportState.GENERATED, {ReportState.CREATED}, "generate")

    def mark_generated(self) -> None:
        self.generate()

    def export(self) -> None:
        self._transition(ReportState.EXPORTED, {ReportState.GENERATED}, "export")

    def archive(self) -> None:
        self._transition(ReportState.ARCHIVED, {ReportState.EXPORTED}, "archive")

    def _transition(self, target: ReportState, allowed: set[ReportState], operation: str) -> None:
        if self.state not in allowed:
            raise invalid_transition(
                "report", self.state.value, operation, tuple(state.value for state in allowed)
            )
        self.state = target


def _identity(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise domain_invariant(f"{field} must be a non-empty string", field=field, value=value)
    return value.strip()


ReportStatus = ReportState

__all__: tuple[str, ...] = ()
