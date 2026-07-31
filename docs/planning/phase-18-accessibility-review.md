# Phase 18 Accessibility Review

**Date:** 2026-07-31
**Surfaces:** Workspace shell, command palette, Search (Tabulator), theme control, timeline,
viewer chrome

## Automated coverage

| Gate | Command / artifact |
|------|--------------------|
| Keyboard-only primary workflows | `LUMORA_E2E=1 uv run pytest -m e2e tests/test_phase18_a11y_e2e.py` |
| Existing viewer no-round-trip smoke | `tests/test_phase13_viewer_e2e.py` |

Scenarios covered without mouse APIs after navigation: command palette open/navigate/activate/
close with focus restoration; theme selection including high-contrast; Search input focus;
explorer collapse via keyboard; timeline region focus; cine control activation.

## High contrast and scalable typography

- Runtime `theme` setting accepts `system` \| `light` \| `dark` \| `high-contrast`.
- Workspace theme control is a `<select>` reaching every value (replaces binary toggle).
- CSS defines `:root[data-theme="high-contrast"]` and honors `prefers-contrast: more` under
  `system`.
- Root font-size remains `15px`; 200% browser zoom operability was checked manually on the
  reference desktop: primary toolbar, Search, and dock remain operable; focus rings stay
  visible; horizontal scroll limited to tabular Search/metadata regions.

## Screen reader / semantics

Reference pairing documented: **VoiceOver + Safari** (macOS) on the workspace shell.

Checked:

- Landmarks: `banner`, `main`, Search `role="search"`, dock regions
- Command palette dialog name (`aria-label`)
- Panel collapse `aria-expanded`
- Search result host labeled as a grid; result count live region via `data-search-status`
- Dropped-event counter remains in the status bar live region
- Color is not the sole carrier for retention/state text (labels retained)

### Findings

| Severity | Issue | Workaround / disposition |
|----------|-------|--------------------------|
| Non-blocking | Tabulator remote pagination chrome inherits vendor ARIA; keyboard row nav depends on Tabulator keybindings | Documented; Search input and kind filters remain keyboard operable |
| Non-blocking | Viewer canvas empty state is `role="img"` without live pixel content | Expected until an instance is selected |

No WCAG certification claim is made.

## Explicit non-claims

- Not a universal screen-reader support guarantee
- Not a WCAG conformance certificate
