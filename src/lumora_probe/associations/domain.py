"""Plain-Python association aggregates and their lifecycle rules."""

from __future__ import annotations

from enum import StrEnum

from lumora_probe.shared.errors import domain_invariant, invalid_transition
from lumora_probe.shared.value_objects import (
    AETitle,
    NetworkEndpoint,
    PresentationContext,
)


class AssociationState(StrEnum):
    REQUESTED = "requested"
    NEGOTIATING = "negotiating"
    ESTABLISHED = "established"
    REJECTED = "rejected"
    RELEASED = "released"
    ABORTED = "aborted"
    ARCHIVED = "archived"


class Association:
    """One DICOM association leg and its state machine."""

    def __init__(
        self,
        association_id: str,
        calling_ae: AETitle | str,
        called_ae: AETitle | str,
        *,
        local_endpoint: NetworkEndpoint | None = None,
        remote_endpoint: NetworkEndpoint | None = None,
        presentation_contexts: tuple[PresentationContext, ...] = (),
    ) -> None:
        self.association_id = _identity(association_id, field="association_id")
        self.calling_ae = _ae_title(calling_ae)
        self.called_ae = _ae_title(called_ae)
        if local_endpoint is not None and not isinstance(local_endpoint, NetworkEndpoint):
            raise domain_invariant(
                "local_endpoint must be a NetworkEndpoint", field="local_endpoint"
            )
        if remote_endpoint is not None and not isinstance(remote_endpoint, NetworkEndpoint):
            raise domain_invariant(
                "remote_endpoint must be a NetworkEndpoint", field="remote_endpoint"
            )
        contexts = tuple(presentation_contexts)
        if any(not isinstance(context, PresentationContext) for context in contexts):
            raise domain_invariant(
                "presentation_contexts must contain PresentationContext values",
                field="presentation_contexts",
            )
        context_ids = tuple(context.context_id for context in contexts)
        if len(context_ids) != len(set(context_ids)):
            raise domain_invariant(
                "presentation-context IDs must be unique within an association",
                field="presentation_contexts",
            )
        self.local_endpoint = local_endpoint
        self.remote_endpoint = remote_endpoint
        self.presentation_contexts = contexts
        self.state = AssociationState.REQUESTED

    @property
    def id(self) -> str:
        return self.association_id

    @property
    def status(self) -> AssociationState:
        return self.state

    def begin_negotiation(self) -> None:
        self._transition(
            AssociationState.NEGOTIATING, {AssociationState.REQUESTED}, "begin negotiation"
        )

    negotiate = begin_negotiation

    def establish(self) -> None:
        self._transition(AssociationState.ESTABLISHED, {AssociationState.NEGOTIATING}, "establish")

    accept = establish

    def reject(self) -> None:
        self._transition(AssociationState.REJECTED, {AssociationState.NEGOTIATING}, "reject")

    def release(self) -> None:
        self._transition(AssociationState.RELEASED, {AssociationState.ESTABLISHED}, "release")

    def abort(self) -> None:
        self._transition(
            AssociationState.ABORTED,
            {AssociationState.NEGOTIATING, AssociationState.ESTABLISHED},
            "abort",
        )

    def archive(self) -> None:
        self._transition(
            AssociationState.ARCHIVED,
            {AssociationState.RELEASED, AssociationState.REJECTED, AssociationState.ABORTED},
            "archive",
        )

    def _transition(
        self,
        target: AssociationState,
        allowed: set[AssociationState],
        operation: str,
    ) -> None:
        if self.state not in allowed:
            raise invalid_transition(
                "association", self.state.value, operation, tuple(state.value for state in allowed)
            )
        self.state = target


class AssociationPairState(StrEnum):
    PENDING = "pending"
    NEGOTIATING = "negotiating"
    ESTABLISHED = "established"
    RELEASED = "released"
    ABORTED = "aborted"
    ARCHIVED = "archived"


class AssociationPair:
    """A first-class proxy observation containing three separately-owned legs."""

    def __init__(
        self,
        pair_id: str,
        downstream: Association,
        probe_hop: Association,
        upstream: Association,
    ) -> None:
        self.pair_id = _identity(pair_id, field="pair_id")
        self.downstream = _association(downstream, field="downstream")
        self.probe_hop = _association(probe_hop, field="probe_hop")
        self.upstream = _association(upstream, field="upstream")
        leg_ids = (self.downstream.id, self.probe_hop.id, self.upstream.id)
        if len(set(leg_ids)) != len(leg_ids):
            raise domain_invariant(
                "association-pair legs must have distinct association IDs",
                field="legs",
            )
        self.state = AssociationPairState.PENDING

    @property
    def id(self) -> str:
        return self.pair_id

    @property
    def legs(self) -> tuple[Association, Association, Association]:
        return self.downstream, self.probe_hop, self.upstream

    @property
    def status(self) -> AssociationPairState:
        return self.state

    def begin_negotiation(self) -> None:
        self._transition_legs(
            "begin_negotiation", AssociationPairState.NEGOTIATING, {AssociationState.REQUESTED}
        )

    negotiate = begin_negotiation

    def establish(self) -> None:
        self._transition_legs(
            "establish", AssociationPairState.ESTABLISHED, {AssociationState.NEGOTIATING}
        )

    accept = establish

    def release(self) -> None:
        self._transition_legs(
            "release", AssociationPairState.RELEASED, {AssociationState.ESTABLISHED}
        )

    def abort(self) -> None:
        self._transition_legs(
            "abort",
            AssociationPairState.ABORTED,
            {AssociationState.NEGOTIATING, AssociationState.ESTABLISHED},
        )

    def archive(self) -> None:
        self._transition_legs(
            "archive",
            AssociationPairState.ARCHIVED,
            {AssociationState.RELEASED, AssociationState.REJECTED, AssociationState.ABORTED},
        )

    def _transition_legs(
        self,
        operation: str,
        target: AssociationPairState,
        allowed_states: set[AssociationState],
    ) -> None:
        for leg in self.legs:
            if leg.status not in allowed_states:
                raise invalid_transition(
                    "association-pair",
                    leg.status.value,
                    operation,
                    tuple(state.value for state in allowed_states),
                )
        methods = {
            "begin_negotiation": Association.begin_negotiation,
            "establish": Association.establish,
            "release": Association.release,
            "abort": Association.abort,
            "archive": Association.archive,
        }
        method = methods[operation]
        for leg in self.legs:
            method(leg)
        self.state = target


def _identity(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise domain_invariant(f"{field} must be a non-empty string", field=field, value=value)
    return value


def _ae_title(value: AETitle | str) -> AETitle:
    return value if isinstance(value, AETitle) else AETitle(value)


def _association(value: Association, *, field: str) -> Association:
    if not isinstance(value, Association):
        raise domain_invariant(f"{field} must be an Association", field=field, value=value)
    return value


__all__: tuple[str, ...] = ()
