# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Composition service joining association legs with transfer evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException


class EventSource(Protocol):
    """Read-only event query for evidence rows."""

    async def query_events(
        self,
        *,
        correlation_id: str | None = None,
        aggregate_id: str | None = None,
    ) -> tuple[Any, ...]: ...


class AssociationSource(Protocol):
    """Read-only association leg lookup."""

    async def list_legs(self, association_id: str) -> tuple[Any, ...]: ...


@dataclass(frozen=True, slots=True)
class TransferLeg:
    """One leg of a transfer with evidence summary."""

    leg_id: str
    association_id: str
    event_name: str
    sequence: int
    monotonic_ns: int
    duration_ns: int | None
    origin: str
    evidence: tuple[dict[str, Any], ...]


class TransferInspectorService:
    """Joins association legs with receive/persist/decode evidence."""

    def __init__(self, events: EventSource, associations: AssociationSource) -> None:
        self._events = events
        self._associations = associations

    async def inspect(self, association_id: str) -> tuple[TransferLeg, ...]:
        """Return per-leg rows ordered by sequence; exclude client-asserted events."""

        legs = await self._associations.list_legs(association_id)
        result: list[TransferLeg] = []
        for leg in legs:
            leg_id = getattr(leg, "leg_id", None) or getattr(leg, "association_id", str(leg))
            events = await self._events.query_events(
                correlation_id=association_id, aggregate_id=leg_id
            )
            observed = [
                event for event in events if getattr(event, "origin", None) != "client-asserted"
            ]
            ordered = sorted(observed, key=lambda event: getattr(event, "sequence", 0))
            evidence: list[dict[str, Any]] = []
            prev_monotonic: int | None = None
            for event in ordered:
                payload = getattr(event, "payload", {}) or {}
                evidence.append(
                    {
                        "event_name": getattr(event, "event_name", ""),
                        "sequence": getattr(event, "sequence", 0),
                        "monotonic_ns": getattr(event, "monotonic_ns", 0),
                        "payload": dict(payload),
                    }
                )
                prev_monotonic = getattr(event, "monotonic_ns", prev_monotonic)

            anchor = ordered[0] if ordered else None
            anchor_monotonic = getattr(anchor, "monotonic_ns", 0) if anchor else 0
            last_monotonic = prev_monotonic if prev_monotonic is not None else anchor_monotonic
            duration_ns = (
                (last_monotonic - anchor_monotonic) if ordered and len(ordered) > 1 else None
            )
            result.append(
                TransferLeg(
                    leg_id=str(leg_id),
                    association_id=association_id,
                    event_name=getattr(anchor, "event_name", "") if anchor else "",
                    sequence=getattr(anchor, "sequence", 0) if anchor else 0,
                    monotonic_ns=anchor_monotonic,
                    duration_ns=duration_ns,
                    origin=getattr(anchor, "origin", "") if anchor else "",
                    evidence=tuple(evidence),
                )
            )
        result.sort(key=lambda leg: leg.sequence)
        return tuple(result)


def create_transfer_inspector_router(
    inspector: TransferInspectorService | None = None,
) -> APIRouter:
    """Expose transfer inspection under /transfers."""

    router = APIRouter(prefix="/transfers", tags=["transfers"])

    @router.get("/{association_id}")
    async def get_transfer_inspection(association_id: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        if inspector is None:
            raise HTTPException(503, "transfer inspector not mounted")
        legs = await inspector.inspect(association_id)
        return {"association_id": association_id, "legs": [asdict(leg) for leg in legs]}

    return router


__all__: tuple[str, ...] = (
    "TransferInspectorService",
    "TransferLeg",
    "create_transfer_inspector_router",
)
