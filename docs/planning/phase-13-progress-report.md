# Phase 13 Progress Report — Viewer

**Review date:** 2026-07-30
**Status:** Complete — see phase-13-completion-report.md

## Completed work

- Server-side DICOM frame decode with `pylibjpeg`/`pylibjpeg-openjpeg`, executor isolation,
  normalized little-endian 16-bit grayscale output, sidecar metadata, monotonic decode duration,
  and observed `ImageDecoded` evidence.
- Server LRU frame cache and ±2 asynchronous prefetch policy.
- Structured decode failures distinguishing invalid DICOM, unsupported transfer syntax, broken pixel
  data, and frame-range errors.
- Per-instance/per-frame raw pixel and metadata endpoints; no PNG/JPEG pixel re-encoding.
- Build-time custom viewer loader bundle with local window/level, zoom, pan/invert state and no
  interaction round trip.
- Accessible workspace shell with toolbar/navigation, Explorer, Viewer, Inspector, timeline/log
  dock, status bar, collapsible panels, theme control, keyboard focus, and committed assets.
- UID-keyed study provenance service, partial-study capture counts, duplicate SOP Instance UID
  findings with both digests/provenances, offline folder validation, and `fidelity: objects`
  synthetic-capture writer seam.
- Study browser API seam exposing capture-scoped provenance data.

## Files added or modified

See Phase 13 task reports `phase-13-task-t-13-*.md`, commits `bc1a75a` through `9bdf4c7`, and
regenerated `docs/generated/openapi-v1.json`.

## Verification

- Ruff lint: passed.
- Ruff format: passed.
- Import-linter: 7 kept, 0 broken.
- BasedPyright (`core`, `shared`): 0 errors.
- Full suite: **348 passed, 1 skipped**.
- Browser e2e: **1 passed** with `LUMORA_E2E=1`.
- Asset build/check: passed.
- Synthetic decode, executor isolation, cache/prefetch, failure explanation, frame API, workspace,
  provenance, duplicate finding, and folder import tests are included.

## Closeout status

Wave 1 and Wave 2 closeout deliverables are complete. Dashboard, Search, notifications, and Log
Console are deferred as additive views; `phase-13-defer-audit.md` records that no Phase 13 exit
criterion depends on them and that no new ADR is required for this schedule-only deferral.

See `phase-13-completion-report.md` for exit-criterion evidence and quality-gate results.
