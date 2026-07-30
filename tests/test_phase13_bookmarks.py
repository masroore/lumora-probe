"""Phase 13 bookmark persistence API tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from lumora_probe.core.clock import Clock
from lumora_probe.core.config import StartupConfig
from lumora_probe.core.errors import LumoraError
from lumora_probe.core.ids import IdGenerator
from lumora_probe.core.paths import DataPaths
from lumora_probe.core.storage import StorageDatabases
from lumora_probe.studies.repository import BookmarkRepository
from lumora_probe.web.api import create_app
from tests.doubles.clock import ControllableClock
from tests.doubles.ids import SeededIdGenerator

pytestmark = pytest.mark.component

BASE_TIME = datetime(2026, 7, 30, 0, 0, 0, tzinfo=UTC)

_SEED_IDS = tuple(f"018f0d4e-7b6a-7000-8000-{i:012d}" for i in range(100))


def _make_repo(tmp_path: Path) -> BookmarkRepository:
    paths = DataPaths.from_config(StartupConfig(data_dir=tmp_path / "data"))
    databases = StorageDatabases.from_paths(paths, network_detector=lambda _: False)
    databases.initialise()
    clock: Clock = ControllableClock(BASE_TIME)
    ids: IdGenerator = SeededIdGenerator(_SEED_IDS)
    return BookmarkRepository(databases, clock, ids)


@pytest.mark.asyncio
async def test_bookmark_create_list_delete_round_trip(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    bookmark = await repo.add_bookmark(
        name="My Bookmark",
        study_uid="1.2.3.4",
        series_uid="1.2.3.4.1",
        capture_id="capture-1",
        sop_instance_uid="1.2.3.4.1.1",
    )
    assert bookmark.name == "My Bookmark"
    assert bookmark.created_at == BASE_TIME

    listed = await repo.list_bookmarks()
    assert len(listed) == 1
    assert listed[0].bookmark_id == bookmark.bookmark_id

    removed = await repo.remove_bookmark(bookmark.bookmark_id)
    assert removed is True

    listed_after = await repo.list_bookmarks()
    assert listed_after == ()


@pytest.mark.asyncio
async def test_duplicate_bookmark_name_raises_structured_error(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    await repo.add_bookmark(name="Unique Name", study_uid="1.2.3.4")
    with pytest.raises(LumoraError) as exc_info:
        await repo.add_bookmark(name="Unique Name", study_uid="5.6.7.8")
    assert exc_info.value.code == "LUMORA-STUDIES-BOOKMARKS-001"


@pytest.mark.asyncio
async def test_list_bookmarks_filtered_by_capture_id(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    await repo.add_bookmark(name="Capture 1", study_uid="1.2.3.4", capture_id="capture-1")
    await repo.add_bookmark(name="Capture 2", study_uid="5.6.7.8", capture_id="capture-2")
    await repo.add_bookmark(name="Study Only", study_uid="9.10.11.12")

    capture_1 = await repo.list_bookmarks(capture_id="capture-1")
    assert len(capture_1) == 1
    assert capture_1[0].name == "Capture 1"


@pytest.mark.asyncio
async def test_bookmark_api_round_trip(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    application = create_app(bookmark_provider=repo)
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        create_response = await client.post(
            "/api/v1/bookmarks",
            json={
                "name": "API Bookmark",
                "study_uid": "1.2.3.4",
                "capture_id": "capture-1",
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        bookmark_id = created["bookmark_id"]

        list_response = await client.get("/api/v1/bookmarks")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        delete_response = await client.delete(f"/api/v1/bookmarks/{bookmark_id}")
        assert delete_response.status_code == 204

        list_after = await client.get("/api/v1/bookmarks")
        assert list_after.json() == []


@pytest.mark.asyncio
async def test_bookmark_api_duplicate_name_returns_structured_error(
    tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    application = create_app(bookmark_provider=repo)
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        await client.post("/api/v1/bookmarks", json={"name": "Dup", "study_uid": "1.2.3.4"})
        response = await client.post(
            "/api/v1/bookmarks", json={"name": "Dup", "study_uid": "5.6.7.8"}
        )

    # LumoraError with unknown code maps to 500 via the app's error handler,
    # returning the structured error contract (not a raw traceback).
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "LUMORA-STUDIES-BOOKMARKS-001"


@pytest.mark.asyncio
async def test_bookmark_api_delete_missing_returns_404(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    application = create_app(bookmark_provider=repo)
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.delete("/api/v1/bookmarks/does-not-exist")
    assert response.status_code == 404
