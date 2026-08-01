# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.
"""Tests for the Phase 08 collection query policy."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from lumora_probe.web.query import QueryError, QueryPolicy, apply_query, parse_sort


@dataclass(frozen=True, slots=True)
class Item:
    name: str
    state: str
    rank: int


POLICY = QueryPolicy.from_fields(
    sort_fields=("name", "rank"),
    filter_fields=("name", "state"),
)


def value_for(item: Item, field: str) -> object:
    return getattr(item, field)


def test_query_filters_exact_fields_and_plain_text() -> None:
    items = (Item("alpha", "ready", 2), Item("beta", "failed", 1), Item("alphabet", "ready", 3))

    assert apply_query(items, policy=POLICY, value_for=value_for, filter="state:ready") == (
        items[0],
        items[2],
    )
    assert apply_query(items, policy=POLICY, value_for=value_for, filter="alph") == (
        items[0],
        items[2],
    )


def test_query_sort_is_stable_and_supports_multiple_directions() -> None:
    items = (Item("beta", "ready", 2), Item("alpha", "ready", 2), Item("gamma", "ready", 1))

    assert apply_query(items, policy=POLICY, value_for=value_for, sort="-rank,name") == (
        items[1],
        items[0],
        items[2],
    )


def test_query_rejects_undeclared_fields() -> None:
    with pytest.raises(QueryError, match="unsupported sort field"):
        parse_sort("state", POLICY)
    with pytest.raises(QueryError, match="unsupported filter field"):
        apply_query((), policy=POLICY, value_for=value_for, filter="rank:1")
