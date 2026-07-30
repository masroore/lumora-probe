# Phase 14 Task Report — T-14-03-07 evidence linking in UI

**Status:** Complete

## Completed

- Added an Analysis inspector view to the workspace shell.
- Adapted persisted or in-memory findings into a presentation model without importing
  analysis implementation internals into `web/`.
- Resolved each cited finding sequence against the workspace's captured event rows.
- Rendered resolved citations as same-page links to sequence-addressable timeline rows.
- Rendered missing citations as explicit unavailable evidence instead of emitting broken links.
- Added sequence anchors to both the workspace timeline and live timeline partial.
- Preserved the event stream boundary: findings remain presentation data and are never appended
  to `events.jsonl`.

## Verification

- Phase 14 focused suite: **25 passed**.
- Full suite: **420 passed, 2 skipped**; skips are the expected opt-in interop and browser E2E tests.
- Ruff lint and format: passed.
- Import-linter: **7 kept, 0 broken**.
- BasedPyright on the changed web adapter: **0 errors, 0 warnings, 0 notes**.

## Design notes

- Evidence links use event `sequence`, the ordering authority from ADR-0017, rather than wall-clock
  timestamps or event IDs.
- The adapter accepts the analysis contract's `as_dict()` shape and mapping fixtures, keeping the
  web slice independent of `analysis.domain` and `analysis.repository`.
- Invalid or incomplete UI data fails closed for evidence linking: only sequences found in the
  captured event rows become links.

## Next task

Proceed to T-14-03-08, hardening client-asserted exclusion from inference and timing.
