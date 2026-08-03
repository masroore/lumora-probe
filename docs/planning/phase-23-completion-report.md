# Phase 23 Completion Report — Investigation UI

**Date:** 2026-08-03  
**Status:** Complete

## Completed work

- Added capture-backed HTML view models using the existing `ResourceStore` and study
  browser contracts.
- Added bounded Capture and Study projection lists with URL-owned filter, sort, page, and
  page-size state.
- Added Capture, Study, and Instance deep-link views with full-page and HTMX rendering.
- Added explicit capture provenance, partial-study wording, retention state, object links,
  bookmark/report/delete entry points, and ring-buffer promotion controls.
- Added URL-owned global Search over bounded projection and observed-event inputs.
- Replaced static Inspector tabs with identified, ARIA-linked panels for metadata,
  properties, transfer, analysis, and observed event evidence.
- Integrated the server-normalized frame endpoints into an Instance viewer with frame
  stepping, bounded ±2 prefetch requests, cancellation, zoom, pan, window/level, invert,
  cine, fullscreen, keyboard controls, and visible decode remediation.
- Preserved `ImageDisplayed` as a client-asserted event; it is never used as observed
  analysis evidence.
- Rebuilt committed frontend assets.

## Design decisions

- UI composition uses a new `InvestigationProvider` protocol and
  `ResourceInvestigationProvider`; it does not call the REST API over loopback or import
  another slice's repository.
- Existing REST/application contracts remain unchanged. Phase 23 adds presentation
  composition only and leaves replay/report artifact workflows to Phase 24.
- Study and instance views use capture/projection language and do not imply PACS/archive
  authority.
- Viewer state is browser-local. DICOM parsing and pixel decoding remain server-side.

## Files added

- `src/lumora_probe/web/investigation.py`
- `src/lumora_probe/web/templates/views/workspace_content.html`
- `src/lumora_probe/web/templates/views/captures.html`
- `src/lumora_probe/web/templates/views/capture_detail.html`
- `src/lumora_probe/web/templates/views/studies.html`
- `src/lumora_probe/web/templates/views/study_detail.html`
- `src/lumora_probe/web/templates/views/instance_viewer.html`
- `src/lumora_probe/web/templates/views/search.html`
- `assets/source/investigation-controller.js`
- `static/js/investigation-controller.js`
- `tests/test_phase23_investigation.py`

## Files modified

- `src/lumora_probe/web/api.py`
- `src/lumora_probe/web/ui_routes.py`
- `src/lumora_probe/web/ui_context.py`
- `src/lumora_probe/web/templates/base/workspace.html`
- `src/lumora_probe/web/templates/views/platform.html`
- `assets/source/viewer.js`
- `assets/source/app.css`
- `scripts/build-assets.mjs`
- `static/css/app.css`
- `static/js/viewer.js`
- `tests/ui_inventory.py`

## Verification

- Phase 13, 21, 22, and 23 focused suites: **71 passed, 3 skipped**.
- Ruff check: passed.
- Ruff format check: passed for changed Python files.
- Basedpyright: passed with zero errors, warnings, or notes for changed application modules.
- Frontend assets rebuilt with `npm run build:assets`.

## Known limitations

- Report generation, artifact preview/download, and durable report operation UI remain
  Phase 24 scope.
- Bookmark removal remains exposed through the existing REST contract; Phase 24 owns the
  shared confirmation and duplicate-submit workflow.
- Search currently covers projection and observed-event surfaces. Phase 24 may extend it
  to operations, reports, plugins, and audit references where stable providers exist.
- Browser acceptance remains opt-in through `LUMORA_E2E=1` and requires installed
  Playwright browsers.
