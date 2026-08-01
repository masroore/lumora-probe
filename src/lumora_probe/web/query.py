# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""Validated filtering and sorting for REST collection resources."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class QueryError(ValueError):
    """A collection query cannot be applied under the resource policy."""


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True, slots=True)
class SortSpec:
    """One validated sort key."""

    field: str
    direction: SortDirection = SortDirection.ASC


@dataclass(frozen=True, slots=True)
class QueryPolicy:
    """Declared fields a resource permits for sorting and filtering."""

    sort_fields: frozenset[str]
    filter_fields: frozenset[str]

    @classmethod
    def from_fields(
        cls,
        *,
        sort_fields: Iterable[str],
        filter_fields: Iterable[str],
    ) -> QueryPolicy:
        return cls(frozenset(sort_fields), frozenset(filter_fields))


def parse_sort(value: str | None, policy: QueryPolicy) -> tuple[SortSpec, ...]:
    """Parse comma-separated ``field``/``-field`` sort keys."""

    if value is None or not value.strip():
        return ()
    specs: list[SortSpec] = []
    for raw_key in value.split(","):
        key = raw_key.strip()
        if not key:
            raise QueryError("sort contains an empty field")
        direction = SortDirection.DESC if key.startswith("-") else SortDirection.ASC
        field = key[1:] if key[:1] in {"-", "+"} else key
        if not field or field not in policy.sort_fields:
            allowed = ", ".join(sorted(policy.sort_fields))
            raise QueryError(f"unsupported sort field {field!r}; allowed fields: {allowed}")
        specs.append(SortSpec(field=field, direction=direction))
    return tuple(specs)


def parse_filter(value: str | None, policy: QueryPolicy) -> tuple[str | None, str | None]:
    """Parse a plain text filter or an exact ``field:value`` filter."""

    if value is None:
        return None, None
    expression = value.strip()
    if not expression:
        return None, None
    if ":" not in expression:
        return None, expression.casefold()
    field, expected = (part.strip() for part in expression.split(":", 1))
    if field not in policy.filter_fields:
        allowed = ", ".join(sorted(policy.filter_fields))
        raise QueryError(f"unsupported filter field {field!r}; allowed fields: {allowed}")
    if not expected:
        raise QueryError("exact filter value must not be empty")
    return field, expected.casefold()


def apply_query[T](
    items: Sequence[T],
    *,
    policy: QueryPolicy,
    value_for: Callable[[T, str], Any],
    sort: str | None = None,
    filter: str | None = None,
) -> tuple[T, ...]:
    """Filter and stably sort a collection using only declared resource fields."""

    filter_field, filter_value = parse_filter(filter, policy)
    filtered = list(items)
    if filter_value is not None:
        if filter_field is None:
            filtered = [
                item
                for item in filtered
                if any(
                    filter_value in str(value_for(item, field)).casefold()
                    for field in policy.filter_fields
                )
            ]
        else:
            filtered = [
                item
                for item in filtered
                if str(value_for(item, filter_field)).casefold() == filter_value
            ]

    specs = parse_sort(sort, policy)
    for spec in reversed(specs):
        filtered.sort(
            key=lambda item, field=spec.field: _sort_value(value_for(item, field)),
            reverse=spec.direction is SortDirection.DESC,
        )
    return tuple(filtered)


def _sort_value(value: Any) -> tuple[int, str]:
    """Normalize heterogeneous values so sorting never compares unlike types."""

    return (value is None, "" if value is None else str(value))


__all__: tuple[str, ...] = ()
