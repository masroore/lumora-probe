# UI Platform

Phase 21 establishes Lumora Probe's server-rendered browser interaction platform. It does
not implement operational, investigation, replay, report, or settings workflows; those
remain in Phases 22–24.

## Canonical route registry

`src/lumora_probe/web/ui_navigation.py` is the single source for browser route names,
paths, labels, navigation groups, contextual tabs, and parameter names. The registry drives:

- HTML route registration in `ui_routes.py`;
- primary and utility navigation;
- Explorer links;
- the command palette action list;
- contextual tab validation.

`/` is a compatibility entry point and redirects to `/dashboard`. Resource identifiers live
in path segments. Active contextual tabs live in `?tab=<name>`; invalid tabs fall back to the
first route-defined tab.

## Rendering model

Every registered route supports two representations:

- normal requests return the complete shared workspace document;
- requests carrying `HX-Request: true` return the bounded `#workspace-view` fragment and
  out-of-band title/announcement updates.

The same route endpoint and provider context build both representations. HTML routes do not
call the REST API over loopback and do not import slice repositories.

Primary links retain real `href` values for JavaScript-disabled navigation and add HTMX
attributes for in-place navigation. HTMX replaces `#workspace-view` with `outerHTML` and
pushes the canonical URL. Browser back/forward remains URL-owned.

## Browser controllers

Local source modules live in `assets/source/` and generated committed bundles live in
`static/js/`:

- `workspace-controller.js`: active navigation, title and route announcements, HTMX focus,
  panel lifecycle, and versioned layout preferences;
- `tabs-controller.js`: contextual ARIA tabs, roving `tabindex`, keyboard navigation, and
  URL synchronization;
- `dialog-controller.js`: command-palette dialog open/close, Escape handling, and focus
  return;
- `command-palette.js`: action registry rendering and canonical navigation/toggle dispatch.

HTMX and Alpine are loaded from `static/vendor/`; no runtime network or Node installation is
required. Rebuild assets with `npm run build:assets` and verify drift with
`npm run check:assets`.

## Preference safety

Layout preferences use the versioned `lumora.ui.preferences.v1` storage key. Only approved
boolean layout fields are accepted. Storage access and malformed values fail closed. Resource
identifiers, DICOM metadata, event payloads, and investigation state are not written to
browser storage.

## Interaction inventory

`tests/ui_inventory.py` validates rendered HTML for:

- duplicate IDs;
- broken `aria-controls` and `aria-labelledby` references;
- unresolved registered commands;
- visible controls without an owning link, controller marker, form name, or explicit
  disabled state.

This is a static gate. Playwright acceptance covers navigation, history, focus, command
palette navigation, contextual tab keyboard behavior, and reload persistence.
