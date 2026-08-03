# UI Routes Reference

> **Phase 25** — Route, user, and operator documentation.

## Primary navigation routes

| Route | Path | Description |
|-------|------|-------------|
| Dashboard | `/dashboard` | Operational overview: health, metrics, alerts, associations, recent captures |
| Live Monitor | `/live` | Current DICOM activity: timeline, counters, status, operations |
| Captures | `/captures` | Bounded capture list with URL-owned filter, sort, page state |
| Studies | `/studies` | Cross-capture projection list |
| Search | `/search` | URL-owned workspace search over projections and observed events |
| Replay | `/replay` | Replay history, creation, and operation tracking |

## Utility navigation routes

| Route | Path | Description |
|-------|------|-------------|
| Settings | `/settings` | Effective configuration with provenance, locks, and runtime edits |
| Plugins | `/plugins` | Trusted plugin status and manifest disclosure |
| Audit | `/audit` | Immutable activity history with cursor pagination |

## Contextual routes (deep-linked)

| Route | Path | Description |
|-------|------|-------------|
| Capture Detail | `/captures/{capture_id}` | Capture investigation with overview, transfer, analysis, events, report tabs |
| Study Detail | `/studies/{study_uid}` | Study projection with overview, instances, analysis, events tabs |
| Instance Detail | `/instances/{instance_id}` | Instance inspection with metadata, properties, transfer, analysis, events tabs |
| Replay Detail | `/replay/{operation_id}` | Replay progress and result with configuration, progress, events, result tabs |
| Plugin Detail | `/plugins/{plugin_id}` | Plugin inspection with manifest, status, metrics, audit tabs |
| Operation Detail | `/operations/{operation_id}` | Background operation detail |
| Report Detail | `/reports/{operation_id}` | Report state, preview, and artifact download |

## Redirect

| From | To |
|------|-----|
| `/` | 307 redirect to `/dashboard` |

## HTMX fragment rendering

Every route renders both a full-page shell (`workspace.html`) and an HTMX fragment
(`platform_fragment.html`). HTMX requests are identified by the `HX-Request` header.
Fragment responses omit the workspace shell and render only the view content for
targeted out-of-band swaps.

## WebSocket live transport

Two WebSocket endpoints serve different consumers:

- `/ws/ui` — server-rendered HTML fragments for the workspace UI (subscribed per mounted view)
- `/api/v1/events/stream` — canonical JSON envelopes for CLI, plugins, and integrations

## Accessibility

- Skip link to workspace main content
- ARIA landmarks: banner, main, complementary (explorer, inspector), region (viewer, dock)
- Context tabs with roving tabindex, Home/End/Arrow-key navigation, URL state
- Command palette accessible via keyboard (Ctrl+K / Cmd+K)
- Theme selection: System, Light, Dark, High Contrast
- Explorer and inspector panels collapsible via keyboard
- Viewer controls disabled with explicit cause when unsupported

## Responsive breakpoints

| Breakpoint | Behavior |
|-----------|----------|
| > 980px (desktop) | Full three-column layout: explorer, viewer, inspector |
| 701–980px (tablet) | Nav wraps; explorer and inspector narrow |
| ≤ 700px (narrow) | Panel bodies hidden except viewer; bottom dock single-column |
| ≤ 800px | Operational grid collapses to single column |
