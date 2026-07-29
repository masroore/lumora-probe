# ADR-0029: Capture Deletion Recomputes Projections and Preserves Study-Level References

- **Status:** Accepted
- **Date:** 2026-07-29

## Context

ADR-0004 makes capture directories the permanent evidence and `index.db` a rebuildable
projection. ADR-0013 permits one Study UID to span multiple captures, while bookmarks,
findings, and reports may refer to evidence from a specific capture. Deleting one of
three captures cannot be allowed to make the remaining study appear complete or leave
references that silently point at different bytes.

Phase 06 requires an explicit decision and a test for this three-capture case.

## Decision

Capture deletion has these semantics:

1. The capture directory and its object bytes are deleted. Its `captures`, `instances`,
   and `event_window` index rows are removed through the capture foreign-key cascade.
2. Study and Series rows are recomputed from all surviving instance rows. A Study with
   instances in two or more captures remains visible and is marked `partial`; its
   capture and instance counts reflect surviving provenance. A Study disappears only
   when no instances remain.
3. A bookmark tied to a capture or a capture-scoped SOP Instance is deleted. A
   study-level bookmark with no `capture_id` is retained because its subject may still
   exist in another capture.
4. Findings and reports retain their authoritative record, but never rewrite evidence
   provenance to a surviving capture. Their owning repositories must expose the missing
   capture as an explicit `missing_source` condition. During Phase 06, before those
   repositories exist, the cascade audit records zero materialized finding/report rows
   and the missing capture ID; later repositories consume that audit contract.
5. Every deletion writes a durable `CaptureDeleted` audit record containing affected
   studies, removed instance/bookmark counts, and the explicit cascade policy. No
   deletion is permitted outside configured writable capture roots.

The operation is not auto-resumed or silently repaired. If the index is interrupted,
rebuild from surviving capture directories is authoritative.

## Alternatives considered

- **Delete the whole Study.** Rejected: it hides surviving evidence and violates the
  projection model.
- **Retain capture-scoped bookmarks as dangling records.** Rejected: a bookmark to a
  deleted object cannot be opened and would create an unexplained failure later.
- **Rebind findings/reports to a surviving capture.** Rejected: the bytes and protocol
  provenance may differ; rewriting evidence would falsify an investigation.
- **Keep deleted capture objects in a global store.** Rejected: it creates a second
  source of truth and turns the product into an archive.

## Consequences

- Deletion requires projection recomputation, not only SQL `ON DELETE CASCADE`.
- Study-level bookmarks remain useful while correctly reflecting partial evidence.
- Findings and reports need a visible missing-source state when their persistence slices
  are implemented.
- `app.db` audit history is authoritative and must be backed up; `index.db` remains
  disposable.

## References

ADR-0004 · ADR-0011 · ADR-0013 · ADR-0023 · `01-work-breakdown-structure.md` §2.4
and §C-06 · `02-phase-plan.md` §Phase 06
