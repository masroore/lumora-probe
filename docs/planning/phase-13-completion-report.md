# Phase 13 Completion Report — Viewer

**Review date:** 2026-07-30
**Status:** Complete
**Phase:** 13 — Viewer

## Completed work

Phase 13 delivers server-owned DICOM decoding and a browser viewer that renders normalized
frames without moving decode or window/level work onto the event loop or across a network
round trip.

- Server-side decode uses the existing executor boundary, normalized 16-bit grayscale output,
  sidecar metadata, LRU caching, bounded prefetch, decode duration evidence, and structured
  failure explanations.
- Frame and metadata APIs expose per-instance/per-frame data without PNG/JPEG re-encoding.
- Custom viewer assets provide window/level, zoom, pan, invert, cine, fullscreen, command palette,
  and accessible workspace controls. The Playwright e2e gate verifies local W/L interaction.
- Study Browser projections expose partial-study state, per-instance provenance, duplicate SOP
  Instance UID findings with both digests, retention state, and inline promotion.
- Live ring-buffer object records are joined to the browser on every request by digest. Promotion
  windows use aggregate-scoped earliest/latest event times, expiry is computed per record, and
  digest collisions keep the latest expiry.
- Verified capture objects resolve through the file-backed `DicomObjectSource` adapter.
- Capture summary export carries observed decode duration while excluding client-asserted events.
- `ImageDisplayed` is posted as quarantined client-asserted evidence.
- Event Timeline synchronization is sequence-based; Live Monitor exposes active associations and
  dropped-event counters; Transfer Inspector joins per-leg evidence; bookmarks provide browser/API
  round-trip persistence.
- Offline folder import materializes synthetic captures at `fidelity: objects`; protocol replay
  remains guarded by fidelity.

## Design decisions

- Composition that joins `captures` and `studies` remains in `web/`; domain and slice boundaries
  are unchanged.
- Ring-buffer retention is transient and recomputed per browser request. No retention map is cached.
- Retention is keyed by SHA-256 object digest. Existing permanent projection metadata is preserved
  when no live ring-buffer record matches.
- Client-asserted viewer events remain quarantined from timing, findings, and reports.
- Cornerstone3D remains renderer-only; client-side interaction stays local.
- Dashboard, Search, notifications, and Log Console are deferred as additive views. The deferral
  is documented in `phase-13-defer-audit.md`; no exit criterion depends on these panels.

## Files added or materially modified

- `src/lumora_probe/web/retention.py`
- `src/lumora_probe/web/api.py`
- `src/lumora_probe/web/study_routes.py`
- `src/lumora_probe/studies/repository.py`
- `src/lumora_probe/studies/service.py`
- `src/lumora_probe/reports/contracts.py`
- `src/lumora_probe/reports/service.py`
- `src/lumora_probe/web/report_routes.py`
- `src/lumora_probe/web/bookmark_routes.py`
- `src/lumora_probe/web/transfer_inspector.py`
- `src/lumora_probe/web/live.py`
- `src/lumora_probe/web/templates/workspace.html`
- `assets/source/viewer.js`
- `assets/source/command-palette.js`
- `static/` rebuilt assets
- Phase 13 component and browser tests under `tests/test_phase13_*.py`
- `docs/generated/openapi-v1.json`
- `docs/architecture-baseline/19-glossary.md`
- `docs/adr/ADR-0031-browser-e2e-test-tooling.md`

## Tests and quality gates

- Full default suite: **395 passed, 2 skipped**.
  - One skip is opt-in external implementation interop (`LUMORA_INTEROP=1`).
  - One skip is the opt-in browser gate (`LUMORA_E2E=1`).
- Browser gate: **1 passed** with `LUMORA_E2E=1` after installing Chromium through Playwright.
- Ruff lint: passed.
- Ruff format check: passed.
- Import-linter: **7 kept, 0 broken**.
- BasedPyright strict check for `src/lumora_probe/core` and `src/lumora_probe/shared`:
  **0 errors, 0 warnings, 0 notes**.
- Asset build and drift check: passed.

## Exit-criterion evidence

| Exit criterion | Evidence |
|---|---|
| Decode duration appears in a capture and report | `test_decode_normalizes_frame_and_publishes_duration_evidence`; `test_decode_duration_appears_in_exported_report` |
| Study spanning three captures never renders as whole | `test_study_browser_endpoint_exposes_partial_provenance`; workspace partial-study rendering |
| Ring-buffer instances show retention and offer promotion | `test_retention_map_builds_digest_keyed_entries`; `test_study_browser_endpoint_shows_ring_buffer_retention`; workspace promotion test |
| Duplicate UID finding contains both digests | `test_study_browser_surfaces_capture_provenance_and_duplicate_finding` |
| W/L stays within 100 ms with no round trip | `test_window_level_drag_makes_no_frame_requests` under `LUMORA_E2E=1` |
| Decode failures explain why | `test_invalid_dicom_explains_failure_category` plus structured decode failure tests |

## Known limitations and follow-up

- Interop checks remain opt-in and require the external Docker implementations described by the
  testing strategy.
- Deferred workspace panels are scheduled for a later phase; implementing them requires updating
  the plan before work begins.
- Full report generation, redaction, and export policy remain owned by Phase 15; Phase 13 only adds
  the minimal decode-timing summary needed for the viewer exit criterion.

## Commits

Phase 13 implementation is represented by the task commits from `08c21e4` through the Phase 13
closeout commits, including `a320191` for the live retention composition fix. The working tree is
clean except for the pre-existing untracked local `node_modules/` directory.
