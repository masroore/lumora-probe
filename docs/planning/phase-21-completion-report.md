# Phase 21 — UI Platform Completion Report

**Date:** 2026-08-02  
**Status:** Complete  
**Governing plan:** `docs/planning/02-phase-plan.md` §Phase 21  
**Implementation baseline:** `docs/other/ui-completion-implementation-plan-2026-08-02.md`

## Completed work

### Canonical routes and shell

- Added one immutable route registry for primary, utility, and contextual routes.
- Added canonical HTML routes for Dashboard, Live Monitor, Captures, Studies, Search, Replay,
  Settings, Plugins, Audit, and contextual resource/operation/report paths.
- Changed `/` to a 307 redirect to `/dashboard`.
- Added shared full-page and HTMX fragment composition using one route endpoint and one UI
  context builder.
- Added real `href` values, HTMX targets, URL push behavior, active-route state, utility
  navigation, and contextual route metadata.
- Added explicit route-owned empty/provider-unavailable messaging for the workflow surfaces
  that are implemented in later phases.

### Browser interaction platform

- Added local HTMX and Alpine runtime loading through the committed asset pipeline.
- Added workspace navigation lifecycle handling, focus restoration, title updates, live route
  announcements, and duplicate-listener protection.
- Added contextual ARIA tabs with URL state, roving `tabindex`, Home/End/Arrow-key behavior,
  and reload persistence.
- Added versioned, fail-safe layout preference storage without storing investigation data.
- Added command palette rendering from the canonical action registry, including canonical
  route navigation and panel-toggle actions.
- Added accessible dialog open/close, Escape handling, and focus return behavior.
- Disabled unsupported viewer controls with explicit causes instead of leaving inert buttons.

### Verification

- Added the rendered HTML interaction inventory.
- Added route/fragment coverage across every registered route, redirect coverage, valid and
  invalid tab coverage, duplicate-ID/ARIA/command/inert-control checks, and browser tests.
- Added the UI platform architecture guide at `docs/guides/ui-platform.md`.

## Files added

- `src/lumora_probe/web/ui_actions.py`
- `src/lumora_probe/web/ui_context.py`
- `src/lumora_probe/web/ui_navigation.py`
- `src/lumora_probe/web/ui_routes.py`
- `src/lumora_probe/web/templates/base/workspace.html`
- `src/lumora_probe/web/templates/views/platform.html`
- `src/lumora_probe/web/templates/views/platform_fragment.html`
- `assets/source/workspace-controller.js`
- `assets/source/tabs-controller.js`
- `assets/source/dialog-controller.js`
- `tests/ui_inventory.py`
- `tests/test_phase21_ui_routes.py`
- `tests/test_phase21_ui_browser.py`
- `docs/guides/ui-platform.md`
- `docs/planning/phase-21-completion-report.md`

## Files modified

- `src/lumora_probe/web/api.py`
- `src/lumora_probe/web/workspace_routes.py`
- `assets/source/command-palette.js`
- `assets/source/app.css`
- `scripts/build-assets.mjs`
- `static/js/command-palette.js`
- `static/js/workspace-controller.js`
- `static/js/tabs-controller.js`
- `static/js/dialog-controller.js`
- `static/css/app.css`
- `tests/test_phase13_workspace.py`
- `tests/test_phase14_analysis.py`
- `tests/test_phase18_search.py`
- `tests/test_phase19_no_outbound.py`

## Quality gates

| Gate | Result |
|---|---|
| Full repository suite | `560 passed, 19 skipped` |
| Phase 21 focused/component suite | `41 passed, 2 skipped` |
| Chromium browser acceptance (`LUMORA_E2E=1`) | `2 passed` |
| Ruff lint | Pass |
| Ruff format check | Pass |
| Basedpyright | `0 errors, 0 warnings, 0 notes` |
| Import-linter | `7 kept, 0 broken` |
| Committed asset rebuild | Pass after generated assets are committed |
| Interaction inventory | Pass; negative cases reject violations |

## Design decisions

- No SPA framework, client-side DICOM parsing, loopback HTTP composition, or new runtime
  dependency was introduced.
- The route registry is web composition infrastructure, not a replacement for slice
  contracts. Workflow providers remain injected and are implemented by later phases.
- Existing workspace data rendering remains available in the shared shell for compatibility;
  Phase 22–24 routes add their real provider-backed first paints and mutations.
- Unsupported visible viewer operations are disabled with a cause/remediation rather than
  represented as inert controls.
- No ADR was required; implementation follows ADR-0012, ADR-0019, ADR-0025, and ADR-0031.

## Known limitations

- Dashboard, Live Monitor, investigation, replay, report, settings, plugin, audit, and
  operations data providers are not expanded by Phase 21. Their canonical platform routes
  intentionally expose the shell and an honest unavailable/empty state until their approved
  phase.
- Browser acceptance currently executes on Chromium. Cross-engine qualification remains a
  Phase 25 activity.
- `/ws/ui` live browser transport remains Phase 22 work; Phase 21 establishes the route and
  controller seam without inventing live protocol behavior.

## Implementation commits

- `7377ec9` — canonical UI route registry
- `547cc4e` — shared canonical workspace route composition
- `d269839` — local workspace interaction controllers and generated assets
- final Phase 21 interaction hardening commit — route target, focus, utility navigation,
  inventory, browser acceptance, and completion documentation
