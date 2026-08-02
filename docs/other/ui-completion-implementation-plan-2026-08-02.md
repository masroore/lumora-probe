# Lumora Probe UI Completion Implementation Plan

**Date:** 2026-08-02  
**Status:** Approved planning baseline; implementation not started  
**Scope:** Post-GA Phases 21–25  
**Historical release:** v0.1.0 remains signed off on 2026-07-31  

## 1. Purpose

Complete the browser UI as a working engineering workstation. The current shell renders
navigation, tabs, controls, live placeholders, and workflow affordances whose browser-side
behavior is incomplete or absent. This plan makes every exposed element functional,
addressable, accessible, testable, and backed by an approved application contract.

This is a remediation and completion plan. It does not reopen the v0.1.0 historical
sign-off or change the product into a single-page application, PACS archive, diagnostic
viewer, plugin marketplace, or multi-user system.

## 2. Confirmed current gaps

The following gaps were reproduced against the real FastAPI application in headless
Chromium on 2026-08-02:

- Primary navigation links change only `location.hash`; Dashboard, Live Monitor, Captures,
  Studies, and Replay point to IDs absent from the DOM.
- Search works only as native fragment scrolling because it happens to have a matching ID.
- `aria-current="page"` and Explorer active state remain hardcoded on Dashboard.
- Inspector buttons expose ARIA tab roles without selection behavior, panel association, or
  complete panels.
- `/dashboard` exists, but the workspace links to `#dashboard`.
- Live Monitor contains empty out-of-band fragment targets, but the page loads neither an
  HTMX client nor a `/ws/ui` browser adapter.
- The server-side live governor and partial templates are tested independently; no browser
  test proves mounting, fragment application, reconnection, or navigation.
- Visible viewer and command-palette controls are not governed by one interaction registry,
  allowing controls and commands to drift into inert placeholders.

No browser console or page error occurred during reproduction. The failure is missing
integration behavior, not a JavaScript crash or intercepted pointer event.

## 3. Governing decisions

Implementation must remain within accepted architecture:

- ADR-0012: `web/` owns composition and presentation; slices do not import `web`.
- ADR-0015: server decodes pixels; the browser renders normalized pixels only.
- ADR-0019: HTMX/server-rendered HTML is the primary UI model; `/ws/ui` sends targeted
  server-rendered fragments; local viewer state is the deliberate exception.
- ADR-0020: startup settings are immutable; supported runtime settings are editable with
  provenance.
- ADR-0021: plugins are trusted in-process code; no API installation.
- ADR-0025: Node is build-time only; built assets are committed and packaged.
- ADR-0031: Playwright is the browser acceptance tool.
- ADR-0009/0010: no outbound telemetry, loopback default, and explicit network-exposure
  acknowledgment remain intact.

No new ADR is required for this plan. A new ADR is required before any later attempt to add
SPA routing, client-side DICOM parsing, API plugin installation, auth/RBAC, diagnostic
measurement tools, or a conflicting frontend dependency strategy.

## 4. Accepted product decisions

1. `/` redirects to canonical `/dashboard`.
2. Dashboard, Live Monitor, Captures, Studies, Search, and Replay are real server-rendered
   routes enhanced by HTMX.
3. All pages share one workspace shell; full requests render the shell and HTMX requests
   replace its main view.
4. Resource selection belongs in paths. Filters, sorting, pagination, and active subviews
   belong in query parameters. Browser/server UI sessions do not own investigation state.
5. Primary navigation remains focused. Settings, Plugins, and Audit are utility
   navigation. Reports, Bookmarks, retention, metadata, and transfer inspection remain
   contextual.
6. HTMX owns server interactions. Small dedicated controllers own navigation, tabs,
   live transport, viewer-local state, dialogs, and focus management. No SPA framework or
   general client data store is introduced.
7. One `/ws/ui` connection exists per browser tab and survives HTMX view transitions.
8. No visible inert control is permitted. Unsupported behavior is omitted or disabled with
   a cause and remediation.
9. Inspector tabs are contextual to the selected resource.
10. `/live` is the complete monitor. The shared dock carries Timeline, Logs, and
    Background Operations rather than a duplicate Live Monitor.
11. Dashboard is an observational summary with links to dedicated workflows.
12. Captures use the existing listener/ring-buffer lifecycle; no manual capture-start API
    is invented.
13. Studies remain cross-capture projections with explicit provenance and retention.
14. Search is URL-driven and navigates to canonical resource routes.
15. Replay receives the missing REST/application composition needed for safe event and
    protocol replay workflows.
16. Settings display all effective values but edit only permitted runtime settings.
17. Plugins support list, inspect, enable, and disable only.
18. Audit and Operations receive bounded list/filter contracts required by their UI.
19. Destructive, network-writing, and trust-changing actions require accessible
    confirmation.
20. WCAG 2.2 AA is the accessibility target.
21. Comprehensive Playwright coverage is a mandatory dedicated CI gate.
22. Existing visual language is retained; this is not a brand redesign.
23. Current stable Chromium, Firefox, and WebKit are supported on desktop, with tablet
    reflow and basic narrow-screen operation.
24. Theme is an installation runtime setting. Layout preferences are versioned browser
    preferences. Investigation identifiers are never persisted in browser storage.
25. Viewer scope is engineering inspection only: zoom, pan, window/level, invert, cine,
    frame stepping, and fullscreen. Measurements, annotations, MPR, and client DICOM
    parsing remain excluded.
26. The command palette is generated from the same route/action registry as visible UI.
27. Report generation includes operation tracking, artifact retrieval, preview, and
    download.
28. Failures remain visible with cause and remediation; background work uses a global
    operation/notification tray.
29. Work is split across Phases 21–25.

## 5. Target information architecture

### 5.1 Primary routes

| Route | Purpose |
|---|---|
| `/` | Temporary compatibility entry; redirects to `/dashboard` |
| `/dashboard` | Health, readiness, listener state, metrics, alerts, recent work |
| `/live` | Active associations, throughput, counters, recent events, drops, alerts |
| `/captures` | Capture list, filters, sorting, pagination, ring-buffer state |
| `/captures/{capture_id}` | Capture investigation workspace |
| `/studies` | Cross-capture Study projection browser |
| `/studies/{study_uid}` | Study/Series/Instance hierarchy with provenance |
| `/instances/{instance_id}` | Canonical frame viewer and instance inspection route |
| `/search` | URL-owned global search |
| `/replay` | Replay history, active work, and creation entry |
| `/replay/{operation_id}` | Replay configuration, progress, audit, and result |

### 5.2 Utility routes

| Route | Purpose |
|---|---|
| `/settings` | Effective settings, provenance, locks, supported runtime edits |
| `/plugins` | Discovered plugins and status |
| `/plugins/{plugin_id}` | Manifest, compatibility, metrics, failures, audit |
| `/audit` | Immutable, filtered audit history |
| `/operations/{operation_id}` | Durable operation detail and supported cancellation |
| `/reports/{operation_id}` | Report state, preview, provenance, and download |

### 5.3 Contextual UI

- Capture: Overview, Transfer, Analysis, Events, Report.
- Study: Overview, Instances, Analysis, Events.
- Instance: Metadata, Properties, Transfer, Analysis, Events.
- Replay: Configuration, Progress, Events, Result.
- Plugin: Manifest, Status, Metrics, Audit.
- No selection: explicit contextual empty state.

The selected Inspector tab uses `?tab=<name>`. Invalid tabs fall back to the first valid tab
and replace the URL rather than adding a bad history entry.

## 6. Rendering and controller architecture

### 6.1 Server composition

Create one base workspace template and route-specific view templates:

```text
src/lumora_probe/web/
  ui_routes.py
  ui_context.py
  ui_navigation.py
  ui_actions.py
  templates/
    base/
      workspace.html
      error.html
    views/
      dashboard.html
      live.html
      captures.html
      capture_detail.html
      studies.html
      study_detail.html
      instance_viewer.html
      search.html
      replay.html
      replay_detail.html
      settings.html
      plugins.html
      plugin_detail.html
      audit.html
      operation_detail.html
      report_detail.html
    components/
      primary_nav.html
      utility_nav.html
      explorer.html
      inspector.html
      tabs.html
      dialog.html
      errors.html
      empty_state.html
      operation_tray.html
      status_bar.html
    partials/
      status.html
      counters.html
      timeline.html
      logs.html
      operations.html
```

Exact file grouping may be compressed where YAGNI permits, but responsibilities must remain
separate: route composition, navigation/action definitions, page templates, reusable
components, and live partials.

HTML routes call injected public contracts/application services directly. They must not:

- issue loopback HTTP calls to the REST API;
- import another slice's repository;
- duplicate business policy in templates or JavaScript;
- reach into FastAPI application state from templates;
- silently substitute empty providers in production composition.

REST and HTML routes share provider/service contracts and validation models so they cannot
develop divergent execution paths.

### 6.2 Full-page and HTMX responses

- Normal request: complete HTML document.
- `HX-Request: true`: route-specific workspace view fragment plus any required
  out-of-band navigation, title, Inspector, status, or operation-tray update.
- Primary links use real `href` values plus `hx-get`, `hx-target`, `hx-push-url`, and
  `hx-swap`.
- Browser back/forward replays the canonical URL and restores selected view/tab/filter.
- JavaScript-disabled navigation remains functional.
- Redirects, 404s, validation failures, unavailable providers, and read-only refusals have
  complete-page and HTMX fragment representations.

### 6.3 Browser controllers

Build source modules under `assets/source/` and commit generated files under `static/js/`:

| Controller | Responsibility |
|---|---|
| `workspace-controller.js` | HTMX lifecycle, active navigation, focus restoration, dock state, route announcements |
| `tabs-controller.js` | ARIA tabs, roving tabindex, arrow/Home/End keys, lazy panel load, URL synchronization |
| `live-monitor.js` | `/ws/ui` connection, mount/resubscribe, heartbeat, fragment validation/application, reconnect/stale state |
| `dialog-controller.js` | Accessible confirmation dialogs, focus trap/return, double-submit prevention |
| `operation-tray.js` | Background operation state, progress, completion/failure announcements, supported cancellation |
| `command-palette.js` | Shared command registry, filtering, shortcuts, context actions |
| `viewer.js` | Viewer-local frame/render/tool state only |

Every controller must support idempotent initialization and teardown across HTMX swaps.
Global listeners and sockets must not multiply after navigation.

### 6.4 State ownership

| State | Owner |
|---|---|
| Current page/resource/filter/sort/page/tab | URL |
| Domain/application state | Server services and stores |
| Live status/counters/timeline | Server governor; rendered fragments |
| Viewer transform/window/cine | Browser viewer controller |
| Theme | Runtime Settings API |
| Panel size/open state/table density/page size | Versioned `localStorage` |
| Patient/study/capture identifiers | Never `localStorage` |
| Operation progress | Durable operation registry plus live updates |

## 7. Live Monitor contract

### 7.1 First paint

The `/live` route and shared status/dock components render meaningful current state before
the socket connects. Empty `hx-swap-oob` placeholders are not acceptable. The same Jinja
partials render first paint and live updates.

### 7.2 Browser protocol

`live-monitor.js` must:

1. Open `ws://` or `wss://` from the current origin at `/ws/ui`.
2. Wait for `ready`.
3. Send `mount` with the canonical page, currently mounted/open known panels, and required
   topics.
4. Validate `mounted`, `fragments`, `ping`, and structured `error` messages by protocol
   version and type.
5. Reply to ping/pong as the server protocol requires.
6. Apply only allowlisted targets (`status`, `counters`, `timeline`, `logs`, `operations`
   after server support lands).
7. Use HTMX processing for out-of-band swaps so newly inserted controls are initialized.
8. Track the highest observed sequence and surface drops/gaps without inventing causality.
9. Resubscribe after route, Inspector, and dock-panel changes.
10. Close cleanly on page unload and avoid duplicate connections after swaps.

### 7.3 Resilience

- States: connecting, live, stale, disconnected.
- Exponential reconnect with jitter and a bounded maximum delay.
- Preserve last content while disconnected and label it stale.
- Manual reconnect action.
- Reset retry delay after a stable connection.
- Re-render current state after reconnect; do not assume missed fragments were delivered.
- Test server restart, offline/online transition, malformed message, unknown target,
  unsupported protocol version, queue drop, rapid navigation, hidden tab, and multiple
  concurrent browser tabs.

## 8. REST/application contract additions

All additions use Pydantic v2 boundary models, stable structured errors, read-only/network
policy enforcement, generated OpenAPI updates, and public slice contracts.

### 8.1 Replay

Add:

- `GET /api/v1/replays`
- `POST /api/v1/replays/preflight`
- `POST /api/v1/replays`
- `GET /api/v1/replays/{operation_id}`
- `POST /api/v1/replays/{operation_id}/cancel`

Creation uses a discriminated request model for event versus protocol replay. Protocol
replay defaults to dry-run, requires an explicit target, respects the configured allowlist,
and preserves existing fidelity/exclusivity/audit rules. Cancellation is exposed only
through the existing cooperative operation mechanism.

### 8.2 Operations

Extend:

- `GET /api/v1/operations` with bounded pagination and state/type filters.
- `POST /api/v1/operations/{operation_id}/cancel` where the registered operation supports
  cancellation.
- Existing `GET /api/v1/operations/{operation_id}` remains stable.

### 8.3 Audit

Extend `GET /api/v1/audit` with bounded cursor/page semantics, stable ordering, and filters
for category, operation, aggregate/capture/replay/plugin identity, and supported date
ranges. Audit remains immutable and read-only.

### 8.4 Reports

Keep capture-scoped report creation and add:

- `GET /api/v1/reports/{operation_id}`
- `GET /api/v1/reports/{operation_id}/artifact`

The artifact response uses the generated media type, safe filename, content disposition,
and explicit missing/failed/expired states.

### 8.5 Search

Extend the existing search composition only where providers support stable results:
captures, operations, reports, plugins, and audit references. Preserve bounded pagination
and virtualization. Do not perform unbounded in-memory fan-in.

## 9. Page requirements

### 9.1 Dashboard

- Health/readiness and listener/admission state.
- Capture, association, event, dropped-event, storage, and operation summaries.
- Active alerts and degraded conditions.
- Recent captures, replay operations, and reports.
- Plugin health summary.
- Canonical links into dedicated workflows.
- No duplicated complex creation/configuration forms.

### 9.2 Live Monitor

- Connection and data freshness state.
- Active associations with calling/called AE, endpoint, state, timing, and linked evidence.
- Throughput, event, error, and drop counters.
- Bounded recent timeline ordered by sequence.
- Alerts and degraded conditions.
- Association selection opens contextual Inspector.
- No end-to-end transfer claims that violate ADR-0003.

### 9.3 Captures

- Bounded list, filtering, sorting, pagination, and empty/unavailable states.
- Capture detail, manifest/provenance, events, transfer evidence, findings, and report state.
- Ring-buffer inventory and explicit promotion confirmation.
- Retention/expiry state.
- Bookmark add/remove.
- Report generation.
- Delete confirmation and read-only refusal.
- Links to Study/Instance projections and viewer.
- No manual capture-start control.

### 9.4 Studies and Instances

- Study → Series → Instance projection hierarchy.
- Every contributing Capture and per-instance provenance.
- Retention state and partial-study honesty.
- Canonical Instance viewer links.
- Context synchronization across Explorer, Viewer, Inspector, and Timeline.
- No PACS/archive language or implication.

### 9.5 Search

- URL-owned query, kinds, filters, ordering, page size, and pagination.
- Incremental request cancellation/debounce.
- Virtualized results.
- Keyboard selection and canonical navigation.
- No duplicated detail application.

### 9.6 Viewer

- Load normalized server-decoded frames.
- Frame selector, next/previous, cine speed, play/pause.
- Zoom, pan, window/level, invert, reset, and fullscreen.
- Current frame and window state.
- Current ±2 frame prefetch with abort/cancellation.
- Loading, unsupported syntax, invalid pixel data, frame range, decode, and renderer errors
  with cause/remediation.
- Keyboard controls and reduced-motion behavior.
- Client-asserted display events remain origin-quarantined.
- No measurements, annotations, MPR, diagnostic claims, or browser DICOM parser.

### 9.7 Replay

- Replay history and active job list.
- Event/protocol mode-specific form.
- Capture/fidelity eligibility and preflight result.
- Dry-run default and prominent non-dry-run confirmation.
- Explicit protocol target and allowlist feedback.
- Timing mode, progress, cancellation, result, and durable audit.
- Active protocol-replay exclusivity and restart-interrupted state.

### 9.8 Reports and Bookmarks

- Generate HTML, Markdown, and JSON reports.
- Track through Operations and live updates.
- Preview/download artifact with provenance and rule-set version.
- Explicit failed/missing/expired states.
- Bookmarks remain capture-context evidence markers, not a primary page.

### 9.9 Settings

- Sections: Network, DICOM, Capture/Retention, Viewer, Analysis, Plugins, Appearance.
- Effective value and source.
- Locked startup/file/environment values with restart remediation.
- Supported runtime edits only.
- Validation before commit; changed values reflected without full reload where safe.
- Configuration change audit evidence.
- No network-exposure gate bypass.

### 9.10 Plugins

- List and detail.
- Manifest, SDK compatibility, declared capabilities, status, health, metrics, failures,
  and audit.
- Enable/disable with confirmation and restart semantics where required.
- Persistent trust disclosure.
- No install/upload/uninstall/sandbox/capability-enforcement claim.

### 9.11 Audit and Operations

- Bounded, filterable, stable lists.
- Correlation and resource links.
- Operation progress/result and supported cancellation.
- Critical failures remain visible until acknowledged.
- No invented authenticated actor identity.

## 10. Shared interaction requirements

### 10.1 Navigation

- Real `href` on every link.
- One route/action registry drives primary nav, utility nav, Explorer, breadcrumbs, and
  command palette.
- Active state derived from canonical route, never hardcoded.
- Direct load, refresh, open-in-new-tab, copy-link, back, and forward work.
- HTMX navigation restores focus to the main heading and announces the new page.

### 10.2 Tabs

- Correct `tablist`, `tab`, and `tabpanel` IDs and relationships.
- Exactly one selected tab where tabs exist.
- Arrow keys, Home, End, Enter/Space as appropriate.
- Roving tabindex and focus preservation.
- Lazy panels expose a loading state and structured failure.
- Invalid/unavailable tabs are omitted, not inert.

### 10.3 Mutations

Accessible confirmation is required for capture deletion, bookmark removal, ring-buffer
promotion, non-dry-run protocol replay, operation cancellation, plugin enable/disable, and
sensitive runtime-setting changes.

Dialogs must:

- state target and impact;
- identify reversibility;
- trap and restore focus;
- disable duplicate submission;
- preserve structured cause/remediation;
- avoid `window.confirm()`.

### 10.4 Feedback

- Inline validation near controls.
- Persistent error blocks with cause and remediation.
- Accessible status regions for success.
- Global operation/notification tray for background work, disconnects, drops, and alerts.
- Explicit loading, empty, disabled, unavailable-provider, stale, read-only, and offline
  states.

## 11. Security and privacy requirements

- Same-origin HTTP/WS policy remains enforced.
- No CDN, telemetry, update check, external font, or outbound browser request.
- Validate and contain every identifier before filesystem access.
- Escape server-rendered evidence by default; no unsanitized fragment injection.
- The live client accepts only known message versions/types, panel names, and target IDs.
- No capture/study/instance identifiers in browser storage.
- Clipboard/export actions are explicit user gestures.
- Preserve evidence fidelity; do not claim de-identification or PS3.15 conformance.
- Read-only mode gates every mutation through the existing central seam.
- Non-loopback deployment continues to require explicit trust acknowledgment and documented
  reverse-proxy security boundary.

## 12. Accessibility and responsive requirements

- WCAG 2.2 AA target.
- Complete keyboard workflows.
- Screen-reader landmarks, names, descriptions, tab semantics, table/grid semantics, dialog
  semantics, status/live regions, and route announcements.
- Visible focus, sufficient contrast, high-contrast theme, scalable typography, 200% zoom,
  and reduced-motion support.
- Desktop-first; large tablet reflow; narrow screens remain usable for monitoring/admin.
- Viewer documents its practical workstation constraint without making navigation
  inaccessible.

## 13. Performance requirements

- Preserve the ratified <100 ms target for local interaction feedback where applicable.
- Use server pagination and Tabulator virtualization for large collections.
- Abort superseded search, Inspector, and frame requests.
- Avoid full-shell redraws for route changes and live updates.
- One live socket per browser tab.
- No listener accumulation after repeated HTMX navigation.
- Viewer prefetch is bounded and decode remains off the event loop.
- Measure route swap latency, large-table responsiveness, live fragment application,
  viewer frame transition, memory growth, and concurrent clients.

## 14. Testing strategy

### 14.1 Static and unit

- Route/action registry uniqueness and target validity.
- URL/query parsing and normalization.
- Tab state and keyboard transitions.
- Live protocol parsing, target allowlist, reconnect/backoff, stale transitions.
- Preference schema/version validation.
- Viewer state and request cancellation.

### 14.2 Component/transport

- Every HTML route: full page and HTMX fragment.
- Canonical redirects, deep links, 404s, structured errors, unavailable providers.
- Replay, operation, audit, report artifact, search, settings, plugin, capture, and bookmark
  contracts.
- `/ws/ui` mount/resubscribe/fragment/error/heartbeat behavior.
- First paint and live update use the same Jinja partials.
- Read-only and network-exposure gates.

### 14.3 Playwright

- Every visible nav item, Explorer item, Inspector tab, command, button, form, dialog, viewer
  tool, dock panel, and operation action works or is intentionally disabled with a reason.
- Direct load, refresh, back/forward, copied URL, open-in-new-tab.
- HTMX navigation without full-page reload.
- One socket across repeated navigation; no duplicated global listeners.
- Live reconnect, server restart, stale state, malformed fragment, drop evidence, rapid
  resubscription, and concurrent tabs.
- Keyboard-only primary workflows.
- Axe checks and manual screen-reader scripts.
- Chromium, Firefox, WebKit; desktop and tablet; narrow-screen monitoring/admin.
- High contrast, reduced motion, zoom, focus restoration.
- No outbound network requests.

### 14.4 Adversarial

- Live channel saturation and gap reporting.
- Rapid route/tab changes with slow responses.
- Duplicate mutation submission.
- Operation completion during navigation.
- Capture expiry/deletion while selected.
- Report artifact expiry.
- Plugin failure during inspection.
- Replay target refusal and exclusivity race.
- Browser storage corruption/version mismatch.

## 15. Phase plan

### Phase 21 — UI Platform

**Objective:** Establish canonical routes, shared shell, controllers, state ownership, and
the test seam that makes inert controls impossible.

**Exit:**

- `/` redirects to `/dashboard`.
- All primary/utility routes render full pages and HTMX fragments.
- Navigation, URL history, contextual tabs, command palette, dialogs, preferences, focus,
  and feedback components work.
- HTMX and Alpine assets are loaded locally through the committed-assets pipeline.
- An automated interaction inventory fails for missing targets, duplicate IDs, invalid ARIA
  relationships, and unowned visible controls.

### Phase 22 — Operational UI

**Objective:** Complete Dashboard, Live Monitor, shared dock, Operations, Audit, metrics,
alerts, and browser live transport.

**Exit:**

- Dashboard and `/live` render meaningful first paint.
- One `/ws/ui` connection mounts/resubscribes and applies allowlisted fragments.
- Reconnect/stale/drop/concurrent-tab scenarios pass.
- Operations tray and Audit pages have bounded working contracts.
- Timeline, Logs, and Operations dock panels synchronize with current context.

### Phase 23 — Investigation UI

**Objective:** Complete Captures, Studies, Search, contextual Inspector, transfer evidence,
metadata, retention, bookmarks, and Viewer.

**Exit:**

- Capture/Study/Instance deep links and browser history work.
- Provenance and retention remain explicit.
- All applicable Inspector tabs have real panels.
- Search remains responsive on large data.
- Every approved viewer control is functional; unsupported input is refused with
  cause/remediation.

### Phase 24 — Controlled Workflows

**Objective:** Complete Replay, Reports, Settings, Plugins, confirmations, and mutation
integration.

**Exit:**

- Event/protocol replay can be preflighted, started, observed, cancelled where supported,
  and audited.
- Non-dry-run writes require explicit target confirmation.
- Reports can be generated, tracked, previewed, and downloaded.
- Settings provenance/locks and plugin trust semantics are accurate.
- Every mutation respects read-only and network policy and prevents duplicate submission.

### Phase 25 — UI Qualification

**Objective:** Prove the completed UI across browser, accessibility, performance, security,
resilience, packaging, and documentation gates.

**Exit:**

- Interaction inventory reports no inert exposed control.
- Chromium, Firefox, and WebKit suites pass.
- WCAG 2.2 AA automated checks and recorded manual checks pass or limitations are explicit.
- Performance/resilience/security measurements pass or are triaged and accepted.
- Asset rebuild produces no drift; installed wheel and Docker UI load without Node,
  network, or CDN.
- Route map, user/operator guidance, known limitations, acceptance matrix, and completion
  reports are published.

## 16. Execution order and parallelism

1. Phase 21 is serial and blocks all later UI work.
2. After Phase 21:
   - Phase 22 Dashboard work may run parallel with its live-client work.
   - Phase 23 Captures and Studies/Search may run parallel until Inspector/Viewer
     integration.
   - Phase 24 Replay contracts may run parallel with Settings/Plugins UI.
3. Phase 22 live transport must finish before operation/replay/report live progress is
   accepted.
4. Phase 23 canonical resource routes must finish before contextual report/bookmark actions
   are accepted.
5. Phase 25 starts only after Phases 21–24 pass their full phase gates.

## 17. Definition of completion

The UI remediation is complete only when:

1. Every visible control is functional or intentionally disabled with a reason.
2. Every resource/workflow has a canonical URL and direct-load behavior.
3. Full-page, HTMX, REST, and WebSocket paths use one application policy.
4. Live first paint and live fragments share templates.
5. No client can silently miss/drop evidence without a visible indication.
6. No unsupported capability silently degrades.
7. Browser back/forward, keyboard use, focus, and accessibility work across complete
   workflows.
8. All generated contracts/assets are current.
9. Full Python quality gates, committed-asset checks, and dedicated browser gates pass.
10. The Phase 25 acceptance report states executed evidence and any unverified item.

## 18. Explicit exclusions

- Authentication, RBAC, multi-user preferences, or user identity.
- Plugin installation/upload/uninstall over API.
- Plugin sandboxing or capability enforcement.
- DICOM de-identification or PS3.15 conformance.
- Diagnostic measurements, annotations, MPR, or clinical interpretation.
- Client-side DICOM parsing.
- pcap import, byte-exact mock-peer replay, remote collectors, Prometheus exposition.
- Brand redesign or migration to React/Vue/Svelte or another SPA framework.

## 19. Documentation deliverables

- Updated canonical Phase 21–25 roadmap, WBS, and implementation order.
- UI route and interaction architecture guide.
- `/ws/ui` browser-adapter protocol guide and regenerated AsyncAPI where applicable.
- User workflows for Dashboard, Live Monitor, Capture investigation, Study/Instance
  inspection, Search, Replay, Reports, Settings, Plugins, Audit, and Operations.
- Accessibility review, performance report, security review, interaction inventory,
  acceptance matrix, and per-phase completion reports.

