# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Plain-Python capture aggregate and its lifecycle rules."""

from __future__ import annotations

from enum import StrEnum

from lumora_probe.shared.errors import domain_invariant, invalid_transition


class CaptureState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    ARCHIVED = "archived"


class Capture:
    """An engineering capture session, including promoted ring-buffer windows."""

    def __init__(
        self,
        capture_id: str,
        *,
        partial: bool = False,
        promoted_from_buffer: bool = False,
        incomplete_aggregates: tuple[str, ...] = (),
        association_ids: tuple[str, ...] = (),
    ) -> None:
        self.capture_id = _identity(capture_id, field="capture_id")
        if not isinstance(partial, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise domain_invariant("partial must be a boolean", field="partial", value=partial)
        if not isinstance(promoted_from_buffer, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise domain_invariant(
                "promoted_from_buffer must be a boolean",
                field="promoted_from_buffer",
                value=promoted_from_buffer,
            )
        self.partial = partial
        self.promoted_from_buffer = promoted_from_buffer
        self.incomplete_aggregates = tuple(
            _identity(aggregate_id, field="incomplete_aggregates")
            for aggregate_id in incomplete_aggregates
        )
        self.association_ids = tuple(
            _identity(association_id, field="association_ids") for association_id in association_ids
        )
        self.state = CaptureState.CREATED
        self.interruption_reason: str | None = None

    @property
    def id(self) -> str:
        return self.capture_id

    @property
    def status(self) -> CaptureState:
        return self.state

    def start(self) -> None:
        self._transition(CaptureState.RUNNING, {CaptureState.CREATED}, "start")

    def stop(self) -> None:
        self._transition(CaptureState.STOPPING, {CaptureState.RUNNING}, "stop")

    def complete(self) -> None:
        self._transition(CaptureState.COMPLETED, {CaptureState.STOPPING}, "complete")

    def interrupt(self, reason: str = "capture interrupted") -> None:
        self._transition(
            CaptureState.INTERRUPTED,
            {CaptureState.CREATED, CaptureState.RUNNING, CaptureState.STOPPING},
            "interrupt",
        )
        self.interruption_reason = _identity(reason, field="reason")

    mark_interrupted = interrupt

    def archive(self) -> None:
        self._transition(
            CaptureState.ARCHIVED,
            {CaptureState.COMPLETED, CaptureState.INTERRUPTED},
            "archive",
        )

    def add_association(self, association_id: str) -> None:
        if self.state is not CaptureState.RUNNING:
            raise invalid_transition("capture", self.state.value, "add association", ("running",))
        identifier = _identity(association_id, field="association_id")
        if identifier not in self.association_ids:
            self.association_ids = (*self.association_ids, identifier)

    def _transition(self, target: CaptureState, allowed: set[CaptureState], operation: str) -> None:
        if self.state not in allowed:
            raise invalid_transition(
                "capture", self.state.value, operation, tuple(state.value for state in allowed)
            )
        self.state = target


def _identity(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise domain_invariant(f"{field} must be a non-empty string", field=field, value=value)
    return value


CaptureStatus = CaptureState

__all__: tuple[str, ...] = ()
