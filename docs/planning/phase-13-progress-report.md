# Phase 13 Progress Report — Viewer

**Review date:** 2026-07-30
**Status:** In progress — not accepted

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
- Asset build/check: passed before the final Python-only study-browser route update; route changes do
  not affect assets.
- Synthetic decode, executor isolation, cache/prefetch, failure explanation, frame API, workspace,
  provenance, duplicate finding, and folder import tests are included.

## Remaining Phase 13 work

- Ring-buffer retention state contract, study browser serialization, and accessible inline promotion action (live ring-buffer-to-provider composition remains).
- Capture-scoped bookmark UI and API action.
- Transfer Inspector with per-leg association and decode/receive evidence.
- Event Timeline synchronization over the live bus, Log Console, Live Monitor, Dashboard, Search,
  command palette, notifications, and client-asserted `ImageDisplayed` post-back.
- Cine playback, fullscreen, and a browser-facing Cornerstone integration test.
- An application adapter joining verified capture objects to `DicomObjectSource` and a complete
  report/export assertion that includes decode timing.

Phase 13 remains open. Do not begin Phase 14 until these deliverables are implemented or explicitly
deferred with architecture-approved documentation and the phase exit criteria pass.
