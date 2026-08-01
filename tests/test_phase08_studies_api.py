# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Tests for Phase 08 study, series, and instance collection routes."""

from __future__ import annotations

import httpx
import pytest

from lumora_probe.web.api import create_app
from lumora_probe.web.resources import InMemoryResourceStore


@pytest.mark.asyncio
async def test_projection_collections_are_exposed_with_consistent_pagination() -> None:
    store = InMemoryResourceStore(
        {
            "studies": {"s1": {"study_uid": "s1", "instance_count": 2}},
            "series": {"r1": {"study_uid": "s1", "series_uid": "r1", "instance_count": 2}},
            "instances": {
                "i1": {
                    "capture_id": "c1",
                    "study_uid": "s1",
                    "series_uid": "r1",
                    "sop_instance_uid": "i1",
                }
            },
        }
    )
    application = create_app(projection_store=store)
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        studies = await client.get("/api/v1/studies")
        series = await client.get("/api/v1/series?filter=study_uid:s1")
        instance = await client.get("/api/v1/instances/i1")

    assert studies.status_code == series.status_code == instance.status_code == 200
    assert studies.json()["items"] == [{"study_uid": "s1", "instance_count": 2}]
    assert series.json()["total"] == 1
    assert instance.json()["sop_instance_uid"] == "i1"
