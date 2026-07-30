"""REST routes for bookmark persistence."""

from __future__ import annotations

from typing import Any, Protocol

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class BookmarkProvider(Protocol):
    """Application provider for bookmark CRUD operations."""

    async def add_bookmark(
        self,
        name: str,
        study_uid: str,
        series_uid: str | None = None,
        capture_id: str | None = None,
        sop_instance_uid: str | None = None,
    ) -> Any: ...

    async def list_bookmarks(self, capture_id: str | None = None) -> Any: ...

    async def remove_bookmark(self, bookmark_id: str) -> bool: ...


class BookmarkCreateRequest(BaseModel):
    """Request body for creating a bookmark."""

    name: str
    study_uid: str
    series_uid: str | None = None
    capture_id: str | None = None
    sop_instance_uid: str | None = None


def create_bookmark_router(provider: BookmarkProvider | None = None) -> APIRouter:
    """Expose bookmark CRUD under /bookmarks."""

    router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])

    @router.post("", status_code=201)
    async def create_bookmark(request: BookmarkCreateRequest) -> Any:
        if provider is None:
            raise HTTPException(status_code=404, detail="Bookmark provider is not configured")
        bookmark = await provider.add_bookmark(
            name=request.name,
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            capture_id=request.capture_id,
            sop_instance_uid=request.sop_instance_uid,
        )
        return _bookmark_to_dict(bookmark)

    @router.get("")
    async def list_bookmarks(capture_id: str | None = None) -> Any:
        if provider is None:
            raise HTTPException(status_code=404, detail="Bookmark provider is not configured")
        bookmarks = await provider.list_bookmarks(capture_id=capture_id)
        return [_bookmark_to_dict(b) for b in bookmarks]

    @router.delete("/{bookmark_id}", status_code=204)
    async def delete_bookmark(bookmark_id: str) -> None:
        if provider is None:
            raise HTTPException(status_code=404, detail="Bookmark provider is not configured")
        removed = await provider.remove_bookmark(bookmark_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Bookmark not found")

    return router


def _bookmark_to_dict(bookmark: Any) -> dict[str, Any]:
    return {
        "bookmark_id": bookmark.bookmark_id,
        "name": bookmark.name,
        "study_uid": bookmark.study_uid,
        "series_uid": bookmark.series_uid,
        "capture_id": bookmark.capture_id,
        "sop_instance_uid": bookmark.sop_instance_uid,
        "created_at": bookmark.created_at.isoformat(),
    }


__all__: tuple[str, ...] = ()
