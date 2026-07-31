"""Phase 18 Search panel API composing existing read contracts."""

from __future__ import annotations

import httpx
import pytest

from lumora_probe.web.api import create_app
from lumora_probe.web.resources import InMemoryResourceStore


@pytest.mark.component
@pytest.mark.asyncio
async def test_search_filters_and_paginates_across_kinds() -> None:
    projections = InMemoryResourceStore(
        {
            "studies": {
                "study-a": {"study_uid": "1.2.3.study-a", "instance_count": 2},
                "study-b": {"study_uid": "1.2.3.study-b", "instance_count": 1},
            },
            "series": {
                "series-a": {
                    "study_uid": "1.2.3.study-a",
                    "series_uid": "1.2.3.series-a",
                    "instance_count": 2,
                }
            },
            "instances": {
                "sop-a": {
                    "study_uid": "1.2.3.study-a",
                    "series_uid": "1.2.3.series-a",
                    "sop_instance_uid": "1.2.3.sop-a",
                }
            },
        }
    )
    events = InMemoryResourceStore(
        {
            "events": {
                "e1": {
                    "event_id": "e1",
                    "event_name": "CStoreReceived",
                    "sequence": 1,
                    "correlation_id": "c1",
                }
            }
        }
    )

    class Logs:
        async def list_logs(self):
            return ({"id": "log-1", "level": "info", "message": "listener ready"},)

    application = create_app(
        projection_store=projections,
        event_store=events,
        log_search_provider=Logs(),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        all_results = await client.get("/api/v1/search", params={"q": "", "page_size": 10})
        filtered = await client.get("/api/v1/search", params={"q": "study-a", "page_size": 50})
        paged = await client.get(
            "/api/v1/search",
            params={"q": "", "kinds": "instances", "page": 1, "page_size": 1},
        )
        bad = await client.get("/api/v1/search", params={"kinds": "widgets"})

    assert all_results.status_code == 200
    assert all_results.json()["total"] == 6
    assert filtered.status_code == 200
    assert filtered.json()["total"] >= 3
    assert all(
        item["kind"] in {"studies", "series", "instances"} for item in filtered.json()["items"]
    )
    assert paged.status_code == 200
    assert paged.json()["total"] == 1
    assert len(paged.json()["items"]) == 1
    assert bad.status_code == 400


@pytest.mark.component
@pytest.mark.asyncio
async def test_workspace_includes_search_panel_and_theme_control() -> None:
    application = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert 'id="search"' in response.text
    assert "data-search-table" in response.text
    assert "data-theme-select" in response.text
    assert "high-contrast" in response.text
    assert "/static/js/search-panel.js" in response.text
    assert "/static/vendor/tabulator.min.js" in response.text
