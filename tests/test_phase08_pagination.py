"""Tests for the Phase 08 REST pagination policy."""

from __future__ import annotations

import pytest

from lumora_probe.web.pagination import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    PaginationParams,
    paginate,
)


def test_pagination_defaults_and_maximum_are_explicit() -> None:
    params = PaginationParams()

    assert (params.page, params.page_size) == (DEFAULT_PAGE, DEFAULT_PAGE_SIZE)
    assert MAX_PAGE_SIZE == 500


def test_pagination_slices_one_based_page_and_reports_metadata() -> None:
    page = paginate(tuple(range(1, 8)), PaginationParams(page=2, page_size=3))

    assert page.items == (4, 5, 6)
    assert page.total == 7
    assert page.total_pages == 3
    assert page.as_dict() == {
        "items": [4, 5, 6],
        "page": 2,
        "page_size": 3,
        "total": 7,
        "total_pages": 3,
    }


@pytest.mark.parametrize(
    ("page", "page_size"),
    ((0, DEFAULT_PAGE_SIZE), (1, 0), (1, MAX_PAGE_SIZE + 1)),
)
def test_pagination_rejects_invalid_bounds(page: int, page_size: int) -> None:
    with pytest.raises(ValueError):
        PaginationParams(page=page, page_size=page_size)
