# Phase 13 Task Report — T-13-03-05 retention state in browser

**Status:** Partial — browser contract and inline action implemented; application composition remains

## Completed

- Added `InstanceRetention`, which carries source, expiry, promotion window, aggregate identity,
  user-facing retention state, and `promotable` status without making Study authoritative.
- Extended `InstanceProvenance` with stable JSON serialization including retention metadata.
- Added `StudyBrowserService.browser()` to build the capture-scoped browser payload from projection
  rows and an injected digest-keyed retention map.
- Added accessible workspace rendering for retained study instances.
- Added an inline promotion action that posts the explicit promotion window and aggregate ID to the
  existing `POST /api/v1/captures/ring-buffer/promote` seam, reports success/failure, and disables
  duplicate submissions while the request is active.

## Remaining

- Wire the retention map from the live ring-buffer object records into the study browser provider.
- Add the application adapter that joins verified capture objects to `DicomObjectSource`; it remains
  a separate Phase 13 integration task.

## Verification

- Focused studies/workspace tests: 7 passed.
- Full suite: 351 passed, 1 skipped.
- Ruff lint and format: passed.
- Import-linter: 7 kept, 0 broken.
- BasedPyright strict gate for `core` and `shared`: 0 errors.
- Asset bundle rebuilt after workspace CSS changes. The repository-level asset drift command is
  expected to report the intentional working-tree change until this task is committed.
