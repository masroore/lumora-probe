# Phase 09 Completion Report — WebSocket Live Updates

**Status:** Complete
**Date:** 2026-07-29
**Phase:** 09 — WebSocket
**Milestone:** M7 — API Complete

## Completed work

- Added `/api/v1/events/stream` for canonical JSON event batches.
- Added `/ws/ui` for server-rendered HTMX-compatible fragments.
- Added topic filtering by event name, aggregate type, and registered event category.
- Added mounted-view subscriptions for UI clients. Clients without mounted panels receive no
  fragments.
- Added a shared event-source adapter and one `LiveUpdateHub` bus subscription feeding both
  WebSocket surfaces.
- Added the configurable `CoalescingGovernor` with:
  - fixed interval flushing (100 ms default);
  - larger JSON and smaller UI client queues;
  - cumulative counters;
  - latest status row per aggregate;
  - capped timeline state;
  - bounded client queues with dropped source sequence accounting;
  - replay from the bounded event history by sequence cursor;
  - render caching for equal panel/page state within one flush.
- Added heartbeat pings, idle timeout, protocol acknowledgements, and reconnect subscription
  resume commands.
- Applied the existing host/origin security policy during WebSocket handshakes.
- Added shared Jinja partials for counters, status, and timeline panels. The same templates
  serve `/ui/partials/{panel}` first paint and WebSocket updates.
- Added deterministic published live-stream contract artifact:
  `docs/generated/asyncapi-v1.json`.
- Added Jinja2 and WebSockets runtime dependencies.
- Preserved import-linter boundaries by injecting a narrow event-source protocol into `web/`;
  `web/` does not import `core.bus` transitively.

## Design decisions

- The WebSocket layer does not construct or own the concrete core event bus. Application
  bootstrap injects an object satisfying `LiveEventSource`. A no-op source keeps the default
  HTTP application factory deterministic until runtime composition supplies the real bus.
- JSON messages are coalesced batches containing unchanged canonical `EventEnvelope` objects;
  the batch wrapper carries replay and drop metadata.
- UI messages contain targeted `hx-swap-oob="outerHTML"` fragments. No client-side rendering
  layer was introduced.
- The app lifespan stops the live hub and its governor. Ownership of an injected event source
  remains with the application bootstrapper.

## Files added

- `src/lumora_probe/web/live.py`
- `src/lumora_probe/web/templates/partials/counters.html`
- `src/lumora_probe/web/templates/partials/status.html`
- `src/lumora_probe/web/templates/partials/timeline.html`
- `scripts/generate_asyncapi.py`
- `docs/generated/asyncapi-v1.json`
- `tests/test_phase09_websocket.py`
- `docs/planning/phase-09-completion-report.md`

## Files modified

- `src/lumora_probe/web/api.py` — injected live event source, app lifespan, live route assembly.
- `src/lumora_probe/web/security.py` — reusable WebSocket host/origin handshake validation.
- `pyproject.toml` — Jinja2 and WebSockets dependencies.
- `uv.lock` — locked dependency graph.

## Tests added

- Canonical JSON stream readiness, topic subscription, and envelope delivery.
- Mounted UI view subscription and targeted HTML fragment delivery.
- Background/unmounted UI suppression through empty panel subscriptions.
- Hostile WebSocket origin rejection.
- First-paint content type and shared partial rendering.
- Sequence-cursor replay.
- UI queue drop accounting with source sequence evidence.
- 5,000-event burst budget.
- AsyncAPI artifact freshness.

## Verification

- Full pytest suite: **281 passed, 1 skipped**.
- Phase 09 tests: **8 passed**.
- Ruff lint and format: passed.
- BasedPyright (`core`, `shared`, `web`, CLI): passed with 0 errors, warnings, and notes.
- Import-linter: **7 contracts kept, 0 broken**.
- Asset checks and package build remain part of the final phase gate.

## Known limitations

- Concrete production composition of the core event bus remains an application bootstrap
  concern; the web factory deliberately uses a no-op source when none is injected.
- UI panel semantics are the Phase 09 generic counters/status/timeline contract. Domain-specific
  panels are added by later viewer, capture, analysis, and reporting phases.
- Resume history is bounded in memory and sequence cursors are interpreted per event source;
  durable replay belongs to later capture/replay phases.
- WebSocket authentication is intentionally absent in accordance with ADR-0009. Host/origin
  checks remain mandatory, and TLS remains a deployment concern.

## Follow-up recommendations

Proceed to Phase 10 only after the final package/assets gates pass. Inject the same live event
source into the DICOM association runtime so real observed traffic appears on both stream
surfaces without introducing a second transport.
