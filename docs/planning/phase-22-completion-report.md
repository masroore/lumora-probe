# Phase 22 — Operational UI Completion Report

**Date:** 2026-08-02  
**Status:** Complete  
**Governing plan:** `docs/planning/02-phase-plan.md` §Phase 22

## Completed work

### Dashboard and Live Monitor first paint

- Replaced inert Dashboard and Live Monitor route content with provider-backed operational
  view models.
- Added readiness/liveness, service/listener health, event-derived metrics, alerts, active
  associations, recent captures, operations, and ordered timeline evidence.
- Preserved the existing Phase 21 workspace shell and full-page/HTMX rendering seam.
- Added explicit empty, degraded, and unavailable states with canonical remediation links.

### Browser live transport

- Added the committed `live-client.js` browser adapter for `/ws/ui`.
- Enforced protocol version validation and visible refusal for malformed commands and unknown
  panels.
- Added mounted-view subscription updates across HTMX navigation.
- Added allowlisted fragment application for `counters`, `status`, `timeline`, and
  `operations`, including shared dock targets.
- Added bounded exponential reconnect with jitter, offline/online handling, stale-state
  marking, heartbeat pong handling, and duplicate-listener prevention.
- Continued to use the existing server coalescing governor and drop-oldest evidence model.

### Operations and Audit

- Added bounded operation list pagination with state/type filters.
- Added cooperative cancellation only for records marked cancellable.
- Added cancellation audit callback wiring in the production composition root.
- Combined in-memory live jobs with durable SQLite operation history for the web read contract.
- Added bounded Audit filters, cursor pagination, immutable read-only rendering, and
  entity/resource links.
- Regenerated `docs/generated/openapi-v1.json`.

## Files added

- `assets/source/live-client.js`
- `src/lumora_probe/web/templates/views/dashboard.html`
- `src/lumora_probe/web/templates/views/live.html`
- `src/lumora_probe/web/templates/views/audit.html`
- `src/lumora_probe/web/templates/partials/operations.html`
- `tests/test_phase22_operational_ui.py`
- `docs/planning/phase-22-completion-report.md`

## Files modified

- Operational providers, UI route composition, live protocol adapter, operation/audit
  contracts, production bootstrap wiring, workspace templates, asset build configuration,
  generated CSS/JavaScript, and generated OpenAPI.

## Tests added

`tests/test_phase22_operational_ui.py` covers:

- provider-backed Dashboard and Live Monitor first paint;
- bounded operation filtering and cancellation auditing;
- read-only, bounded, linkable Audit rendering;
- WebSocket refusal of unknown protocol versions and panel names.

Existing live-stream, concurrent-client, Phase 21 route, operation, audit, and observability
tests remain green.

## Quality gates

- `uv run pytest -q`: passed.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed.
- `uv run basedpyright`: passed.
- `npm run build:assets`: passed.
- OpenAPI artifact synchronization test: passed.

## Known limitations

- The UI live socket remains unauthenticated by design; the existing host/origin and
  loopback/network exposure gates remain authoritative.
- Operation cancellation remains cooperative. A successful request means cancellation was
  requested; final state arrives from the job registry.
- Replay/report-specific workflow pages remain Phase 24 scope. Phase 22 exposes their
  bounded operation evidence and links only.
- Browser qualification across Chromium, Firefox, and WebKit remains Phase 25 scope.

## Follow-up

Phase 23 may reuse the live mounted-view and shared dock seams for capture-backed
investigation. Phase 24 may reuse the bounded operation and cancellation contracts for
replay/report workflows.
