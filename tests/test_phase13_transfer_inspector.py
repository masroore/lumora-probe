# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 13 transfer inspector composition tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import pytest

from lumora_probe.web.api import create_app
from lumora_probe.web.transfer_inspector import (
    TransferInspectorService,
    TransferLeg,
)

pytestmark = pytest.mark.component


@dataclass(frozen=True, slots=True)
class _FakeEvent:
    event_name: str
    sequence: int
    monotonic_ns: int
    origin: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _FakeLeg:
    leg_id: str
    association_id: str


class _FakeEventSource:
    def __init__(self, events: dict[str, tuple[_FakeEvent, ...]]) -> None:
        self._events = events

    async def query_events(
        self,
        *,
        correlation_id: str | None = None,
        aggregate_id: str | None = None,
    ) -> tuple[Any, ...]:
        del correlation_id
        return self._events.get(aggregate_id or "", ())


class _FakeAssociationSource:
    def __init__(self, legs: dict[str, tuple[_FakeLeg, ...]]) -> None:
        self._legs = legs

    async def list_legs(self, association_id: str) -> tuple[Any, ...]:
        return self._legs.get(association_id, ())


def _build_service() -> tuple[TransferInspectorService, str]:
    association_id = "assoc-1"
    legs = (
        _FakeLeg(leg_id="leg-a", association_id=association_id),
        _FakeLeg(leg_id="leg-b", association_id=association_id),
    )
    events = {
        "leg-a": (
            _FakeEvent("AssociationAccepted", 1, 100, "observed", {"caller": "ae-a"}),
            _FakeEvent("ImageDecoded", 3, 300, "observed", {"instance_id": "inst-1"}),
            _FakeEvent("InstancePersisted", 5, 500, "observed", {"path": "/tmp/x"}),
        ),
        "leg-b": (
            _FakeEvent("AssociationAccepted", 2, 200, "observed", {"caller": "ae-b"}),
            _FakeEvent("InstancePersisted", 4, 400, "observed", {"path": "/tmp/y"}),
        ),
    }
    service = TransferInspectorService(
        events=_FakeEventSource(events),
        associations=_FakeAssociationSource({association_id: legs}),
    )
    return service, association_id


@pytest.mark.asyncio
async def test_transfer_inspector_joins_legs_with_evidence() -> None:
    service, association_id = _build_service()
    legs = await service.inspect(association_id)

    assert [leg.leg_id for leg in legs] == ["leg-a", "leg-b"]
    assert legs[0].sequence == 1
    assert legs[1].sequence == 2
    assert legs[0].duration_ns == 400
    assert legs[1].duration_ns == 200
    assert [event["event_name"] for event in legs[0].evidence] == [
        "AssociationAccepted",
        "ImageDecoded",
        "InstancePersisted",
    ]


@pytest.mark.asyncio
async def test_transfer_inspector_excludes_client_asserted_events() -> None:
    association_id = "assoc-2"
    legs = (_FakeLeg(leg_id="leg-c", association_id=association_id),)
    events = {
        "leg-c": (
            _FakeEvent("AssociationAccepted", 1, 100, "observed", {}),
            _FakeEvent("ClientViewed", 2, 200, "client-asserted", {"user": "browser"}),
            _FakeEvent("InstancePersisted", 3, 300, "observed", {}),
        ),
    }
    service = TransferInspectorService(
        events=_FakeEventSource(events),
        associations=_FakeAssociationSource({association_id: legs}),
    )

    result = await service.inspect(association_id)

    assert len(result) == 1
    evidence_names = [event["event_name"] for event in result[0].evidence]
    assert "ClientViewed" not in evidence_names
    assert evidence_names == ["AssociationAccepted", "InstancePersisted"]


@pytest.mark.asyncio
async def test_transfer_inspector_endpoint_returns_legs() -> None:
    service, association_id = _build_service()
    application = create_app(transfer_inspector=service)
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get(f"/api/v1/transfers/{association_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["association_id"] == association_id
    assert len(body["legs"]) == 2
    assert body["legs"][0]["leg_id"] == "leg-a"


@pytest.mark.asyncio
async def test_transfer_inspector_endpoint_503_when_not_mounted() -> None:
    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/api/v1/transfers/any-association")

    assert response.status_code == 503


def test_transfer_leg_dataclass_shape() -> None:
    leg = TransferLeg(
        leg_id="leg-1",
        association_id="assoc-1",
        event_name="AssociationAccepted",
        sequence=1,
        monotonic_ns=100,
        duration_ns=50,
        origin="observed",
        evidence=({"event_name": "AssociationAccepted"},),
    )
    assert leg.leg_id == "leg-1"
    assert leg.duration_ns == 50
