# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Dr. Masroor Ehsan
#
# Part of the Lumora Probe project.
# See the LICENSE file for details.

"""HTML workspace shell route with no application data dependencies."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

WorkspaceData = Mapping[str, Any]
TEMPLATE_ROOT = Path(__file__).with_name("templates")
_MODULE_ROOT = Path(__file__).resolve()
_STATIC_CANDIDATES = (
    _MODULE_ROOT.parents[3] / "static",
    _MODULE_ROOT.parents[2] / "static",
)
STATIC_ROOT = next((path for path in _STATIC_CANDIDATES if path.is_dir()), _STATIC_CANDIDATES[0])

_DEFAULT_WORKSPACE: dict[str, Any] = {
    "title": "Investigation workspace",
    "subtitle": "DICOM engineering observability",
    "active_context": "No capture selected",
    "connection_state": "Ready",
    "events_dropped": 0,
    "explorer_items": (
        {"label": "Dashboard", "detail": "System overview", "active": True},
        {"label": "Live Monitor", "detail": "Associations and throughput", "active": False},
        {"label": "Captures", "detail": "Capture sessions", "active": False},
        {"label": "Studies", "detail": "Projection browser", "active": False},
        {"label": "Search", "detail": "Studies, series, instances, events, logs", "active": False},
        {"label": "Replay", "detail": "Replay jobs", "active": False},
    ),
    "timeline": (),
    "findings": (),
    "logs": (),
    "study_instances": (),
    "metadata": None,
}


def _field(value: object, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value).get(name, default)
    return getattr(value, name, default)


def _finding_dict(finding: object) -> dict[str, Any]:
    as_dict = getattr(finding, "as_dict", None)
    if callable(as_dict):
        value = as_dict()
        if isinstance(value, Mapping):
            return dict(cast(Mapping[str, Any], value))
    if isinstance(finding, Mapping):
        return dict(cast(Mapping[str, Any], finding))
    raise TypeError("workspace findings must provide as_dict() or be mappings")


def _finding_views(
    findings: object,
    events: object,
) -> tuple[dict[str, Any], ...]:
    """Resolve finding citations to anchors for the captured event timeline."""

    if findings is None:
        return ()
    if isinstance(findings, (str, bytes)):
        raise TypeError("workspace findings must be an iterable of finding values")
    finding_values: tuple[object, ...] = (
        tuple(cast(Iterable[object], findings)) if isinstance(findings, Iterable) else ()
    )

    event_by_sequence: dict[int, object] = {}
    if isinstance(events, Iterable) and not isinstance(events, (str, bytes, Mapping)):
        for event in cast(Iterable[object], events):
            sequence = _field(event, "sequence")
            if type(sequence) is int and not isinstance(sequence, bool) and sequence >= 0:
                event_by_sequence.setdefault(sequence, event)

    views: list[dict[str, Any]] = []
    for finding in finding_values:
        value = _finding_dict(finding)
        citations: list[dict[str, Any]] = []
        unresolved: list[int] = []
        sequences = value.get("cited_sequences", ())
        sequence_values = (
            cast(Iterable[object], sequences)
            if isinstance(sequences, Iterable) and not isinstance(sequences, (str, bytes))
            else ()
        )
        for sequence in sequence_values:
            if type(sequence) is not int or isinstance(sequence, bool) or sequence < 0:
                continue
            event = event_by_sequence.get(sequence)
            if event is None:
                unresolved.append(sequence)
                continue
            citations.append(
                {
                    "sequence": sequence,
                    "event_id": _field(event, "event_id", ""),
                    "event_name": _field(event, "event_name", _field(event, "label", "Event")),
                    "href": f"#event-sequence-{sequence}",
                }
            )
        value["evidence_links"] = tuple(citations)
        value["unresolved_sequences"] = tuple(unresolved)
        views.append(value)
    return tuple(views)


def _workspace_context(data: WorkspaceData | None) -> dict[str, Any]:
    """Build a stable, optional-data-only view model for the shell."""

    workspace = dict(_DEFAULT_WORKSPACE)
    if data is not None:
        workspace.update(data)
    workspace["findings"] = _finding_views(workspace.get("findings"), workspace.get("timeline"))
    return {"workspace": workspace}


def create_workspace_router(
    *,
    data: WorkspaceData | None = None,
    template_root: Path | None = None,
) -> APIRouter:
    """Create the root HTML route without reaching into stores or services."""

    del data, template_root
    router = APIRouter(tags=["workspace"])

    @router.get("/", include_in_schema=False)
    def workspace() -> RedirectResponse:  # pyright: ignore[reportUnusedFunction]
        return RedirectResponse("/dashboard")

    return router


__all__ = ["STATIC_ROOT", "WorkspaceData", "create_workspace_router"]
