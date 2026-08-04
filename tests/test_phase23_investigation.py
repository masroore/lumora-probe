# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Phase 23 investigation routes and bounded view-model tests."""

from __future__ import annotations

import httpx
import pytest

from lumora_probe.web.api import create_app
from lumora_probe.web.resources import InMemoryResourceStore
from tests.ui_inventory import validate_interactions


@pytest.fixture
def investigation_stores() -> tuple[
    InMemoryResourceStore, InMemoryResourceStore, InMemoryResourceStore
]:
    captures = InMemoryResourceStore(
        {
            "captures": {
                "capture-1": {
                    "capture_id": "capture-1",
                    "state": "completed",
                    "fidelity": "objects",
                    "created_at": "2026-08-03T00:00:00+00:00",
                    "objects": [
                        {
                            "study_uid": "study-1",
                            "series_uid": "series-1",
                            "sop_instance_uid": "instance-1",
                            "capture_id": "capture-1",
                        }
                    ],
                }
            }
        }
    )
    projections = InMemoryResourceStore(
        {
            "studies": {
                "study-1": {
                    "study_uid": "study-1",
                    "instance_count": 1,
                    "first_seen_at": "2026-08-03T00:00:00+00:00",
                }
            },
            "series": {"series-1": {"study_uid": "study-1", "series_uid": "series-1"}},
            "instances": {
                "instance-1": {
                    "instance_id": "instance-1",
                    "study_uid": "study-1",
                    "series_uid": "series-1",
                    "sop_instance_uid": "1.2.3",
                    "capture_id": "capture-1",
                    "frame_count": 3,
                    "rows": 2,
                    "columns": 2,
                }
            },
        }
    )
    events = InMemoryResourceStore(
        {
            "events": {
                "event-1": {
                    "event_id": "event-1",
                    "event_name": "CStoreReceived",
                    "sequence": 4,
                    "capture_id": "capture-1",
                    "aggregate_id": "instance-1",
                    "origin": "observed",
                }
            }
        }
    )
    return captures, projections, events


@pytest.mark.asyncio
async def test_phase23_deep_links_render_capture_study_instance_and_search(
    investigation_stores: tuple[
        InMemoryResourceStore, InMemoryResourceStore, InMemoryResourceStore
    ],
) -> None:
    captures, projections, events = investigation_stores
    application = create_app(
        capture_store=captures,
        projection_store=projections,
        event_store=events,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        capture = await client.get("/captures/capture-1?tab=events")
        study = await client.get("/studies/study-1?tab=instances")
        instance = await client.get("/instances/instance-1?tab=properties")
        search = await client.get("/search?q=instance-1")

    assert capture.status_code == 200
    assert "CStoreReceived" in capture.text
    assert 'id="tab-events" role="tab"' in capture.text
    assert "capture-backed" in capture.text
    assert study.status_code == 200
    assert "Cross-capture projection" in study.text
    assert "instance-1" in study.text
    assert 'class="context-tabs" data-tabs' in study.text
    assert "Instances (1)" in study.text
    assert instance.status_code == 200
    assert "Frame 0 of 3" in instance.text
    assert "Server-decoded engineering inspection" in instance.text
    assert search.status_code == 200
    assert "/instances/instance-1" in search.text


@pytest.mark.asyncio
async def test_phase23_htmx_investigation_routes_keep_resource_context(
    investigation_stores: tuple[
        InMemoryResourceStore, InMemoryResourceStore, InMemoryResourceStore
    ],
) -> None:
    captures, projections, events = investigation_stores
    application = create_app(
        capture_store=captures,
        projection_store=projections,
        event_store=events,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        response = await client.get(
            "/instances/instance-1?tab=events", headers={"HX-Request": "true"}
        )

    assert response.status_code == 200
    assert "<!doctype html>" not in response.text.lower()
    assert 'data-route-name="instance-detail"' in response.text
    assert 'id="panel-events"' in response.text
    assert "CStoreReceived" in response.text


@pytest.mark.asyncio
async def test_phase23_instance_route_has_real_inspector_panels_and_accessible_controls(
    investigation_stores: tuple[
        InMemoryResourceStore, InMemoryResourceStore, InMemoryResourceStore
    ],
) -> None:
    captures, projections, events = investigation_stores
    application = create_app(
        capture_store=captures,
        projection_store=projections,
        event_store=events,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        response = await client.get("/instances/instance-1")

    assert response.status_code == 200
    for panel in ("metadata", "properties", "transfer", "analysis", "events"):
        assert f'id="inspector-panel-{panel}"' in response.text
        assert f'aria-controls="inspector-panel-{panel}"' in response.text
    validate_interactions(response.text, set())


@pytest.mark.asyncio
async def test_phase23_search_is_bounded_and_url_owned(
    investigation_stores: tuple[
        InMemoryResourceStore, InMemoryResourceStore, InMemoryResourceStore
    ],
) -> None:
    captures, projections, events = investigation_stores
    application = create_app(
        capture_store=captures,
        projection_store=projections,
        event_store=events,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        response = await client.get(
            "/search",
            params={"q": "study-1", "kinds": "studies,instances", "page": 1, "page_size": 1},
        )

    assert response.status_code == 200
    assert 'name="q" value="study-1"' in response.text
    assert 'name="kinds" value="instances,studies"' in response.text
    assert "page 1 of" in response.text
    assert 'name="page_size"' in response.text
