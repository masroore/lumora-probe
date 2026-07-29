"""Plain-Python replay aggregate and replay policy value enums."""

from __future__ import annotations

from enum import StrEnum

from lumora_probe.shared.errors import domain_invariant, invalid_transition
from lumora_probe.shared.value_objects import NetworkEndpoint


class ReplayMode(StrEnum):
    EVENT = "event"
    PROTOCOL = "protocol"


class ReplayFidelity(StrEnum):
    EVENTS = "events"
    PROTOCOL = "protocol"
    WIRE = "wire"


class ReplayState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    ARCHIVED = "archived"


class Replay:
    """A replay execution with explicit mode, fidelity, target, and dry-run policy."""

    def __init__(
        self,
        replay_id: str,
        capture_id: str,
        *,
        mode: ReplayMode | str = ReplayMode.EVENT,
        fidelity: ReplayFidelity | str = ReplayFidelity.EVENTS,
        target: NetworkEndpoint | None = None,
        dry_run: bool = True,
    ) -> None:
        self.replay_id = _identity(replay_id, field="replay_id")
        self.capture_id = _identity(capture_id, field="capture_id")
        self.mode = _enum(mode, ReplayMode, field="mode")
        self.fidelity = _enum(fidelity, ReplayFidelity, field="fidelity")
        if target is not None and not isinstance(target, NetworkEndpoint):
            raise domain_invariant("target must be a NetworkEndpoint", field="target", value=target)
        if not isinstance(dry_run, bool):
            raise domain_invariant("dry_run must be a boolean", field="dry_run", value=dry_run)
        if self.mode is ReplayMode.PROTOCOL and target is None:
            raise domain_invariant(
                "protocol replay requires an explicit target",
                field="target",
                remediation="Configure the protocol replay target; it is never inherited from a capture.",
            )
        if self.mode is ReplayMode.PROTOCOL and self.fidelity is ReplayFidelity.EVENTS:
            raise domain_invariant(
                "protocol replay requires protocol or wire fidelity",
                field="fidelity",
                remediation="Use a capture containing protocol or wire-level evidence.",
            )
        self.target = target
        self.dry_run = dry_run
        self.state = ReplayState.PENDING
        self.interruption_reason: str | None = None

    @property
    def id(self) -> str:
        return self.replay_id

    @property
    def status(self) -> ReplayState:
        return self.state

    @property
    def required_fidelity(self) -> ReplayFidelity:
        return self.fidelity

    def start(self) -> None:
        self._transition(ReplayState.RUNNING, {ReplayState.PENDING}, "start")

    run = start

    def pause(self) -> None:
        self._transition(ReplayState.PAUSED, {ReplayState.RUNNING}, "pause")

    def resume(self) -> None:
        self._transition(ReplayState.RUNNING, {ReplayState.PAUSED}, "resume")

    def complete(self) -> None:
        self._transition(
            ReplayState.COMPLETED, {ReplayState.RUNNING, ReplayState.PAUSED}, "complete"
        )

    def interrupt(self, reason: str = "replay interrupted") -> None:
        self._transition(
            ReplayState.INTERRUPTED,
            {ReplayState.PENDING, ReplayState.RUNNING, ReplayState.PAUSED},
            "interrupt",
        )
        self.interruption_reason = _identity(reason, field="reason")

    mark_interrupted = interrupt

    def archive(self) -> None:
        self._transition(
            ReplayState.ARCHIVED,
            {ReplayState.COMPLETED, ReplayState.INTERRUPTED},
            "archive",
        )

    def _transition(self, target: ReplayState, allowed: set[ReplayState], operation: str) -> None:
        if self.state not in allowed:
            raise invalid_transition(
                "replay", self.state.value, operation, tuple(state.value for state in allowed)
            )
        self.state = target


def _identity(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise domain_invariant(f"{field} must be a non-empty string", field=field, value=value)
    return value


def _enum(value: object, enum_type: type[ReplayMode | ReplayFidelity], *, field: str):
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        choices = ", ".join(member.value for member in enum_type)
        raise domain_invariant(
            f"{field} must be one of: {choices}", field=field, value=value
        ) from exc


ReplayStatus = ReplayState

__all__: tuple[str, ...] = ()
