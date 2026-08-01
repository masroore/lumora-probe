# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Shared pagination policy for REST collection resources."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import Query

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


@dataclass(frozen=True, slots=True)
class PaginationParams:
    """Validated one-based page selection used by collection endpoints."""

    page: int = DEFAULT_PAGE
    page_size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be at least 1")
        if not 1 <= self.page_size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True)
class Page[T]:
    """A page of collection items with stable pagination metadata."""

    items: tuple[T, ...]
    page: int
    page_size: int
    total: int

    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size

    def as_dict(self) -> dict[str, object]:
        return {
            "items": list(self.items),
            "page": self.page,
            "page_size": self.page_size,
            "total": self.total,
            "total_pages": self.total_pages,
        }


def pagination_params(
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> PaginationParams:
    """Build the API pagination policy from validated query parameters."""

    return PaginationParams(page=page, page_size=page_size)


def paginate[T](items: Sequence[T], params: PaginationParams) -> Page[T]:
    """Return the requested page without mutating the source sequence."""

    total = len(items)
    return Page(
        items=tuple(items[params.offset : params.offset + params.page_size]),
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


__all__: tuple[str, ...] = ()
