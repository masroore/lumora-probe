# Phase 24 Completion Report — Controlled Workflows

**Date:** 2026-08-03  
**Status:** Complete

## Completed work

- Added Pydantic replay boundary contracts for event/protocol mode, fidelity, timing,
  explicit target, dry-run, confirmation, preflight, and operation-linked results.
- Added replay REST routes:
  - `GET /api/v1/replays`
  - `POST /api/v1/replays/preflight`
  - `POST /api/v1/replays`
  - `GET /api/v1/replays/{operation_id}`
  - `POST /api/v1/replays/{operation_id}/cancel`
- Composed event replay and protocol replay with the shared in-memory job registry,
  durable operation history, cooperative cancellation, progress events, and replay audit
  persistence.
- Added capture-backed replay input loading in the production composition root.
- Added report status and artifact routes:
  - `GET /api/v1/reports/{operation_id}`
  - `GET /api/v1/reports/{operation_id}/artifact`
- Added JSON report-generation request bodies while preserving the existing query-string
  compatibility form.
- Added safe report media types, filename extensions, inline disposition, `nosniff`, and
  restrictive preview CSP headers.
- Added server-rendered Replay, Report, Settings, Plugins, and Plugin Detail views with
  canonical deep links and HTMX/full-page rendering.
- Added report generation controls to Capture Detail.
- Added shared workflow JavaScript for JSON mutations, confirmation dialogs, in-flight
  duplicate-submit prevention, cancellation, settings updates, and plugin enable/disable.
- Preserved plugin trust semantics: capabilities are disclosure only; installation,
  upload, uninstall, and sandbox-enforcement claims remain absent.
- Regenerated OpenAPI and committed frontend assets.

## Design decisions

- Replay execution remains owned by `replay/service.py`; `web` imports only public replay
  contracts.
- Replay uses existing ADR-0023 operation/job infrastructure. No second job transport or
  resumable execution path was introduced.
- Protocol replay remains dry-run by default and refuses targets outside the injected
  allowlist. The production composition supplies no implicit target allowlist, so a
  deployment must compose an explicit allowlist before protocol writes can proceed.
- Settings API response compatibility remains unchanged. UI-only view-model enrichment
  derives lock and restart indicators from source/name while runtime updates continue
  through `RuntimeSettingsStore`.
- Report artifact delivery reads only operation-scoped paths owned by `ReportJobService`;
  user-controlled filenames and filesystem paths are never accepted.

## Files added

- `src/lumora_probe/replay/contracts.py` — replay boundary models and capture provider.
- `src/lumora_probe/web/replay_routes.py`
- `src/lumora_probe/web/workflow_views.py`
- `src/lumora_probe/web/templates/views/replay.html`
- `src/lumora_probe/web/templates/views/replay_detail.html`
- `src/lumora_probe/web/templates/views/report_detail.html`
- `src/lumora_probe/web/templates/views/settings.html`
- `src/lumora_probe/web/templates/views/plugins.html`
- `src/lumora_probe/web/templates/views/plugin_detail.html`
- `assets/source/workflow-controller.js`
- `tests/test_phase24_workflows.py`

## Files modified

- Replay runtime/application composition.
- `src/lumora_probe/web/api.py`
- `src/lumora_probe/web/report_routes.py`
- `src/lumora_probe/web/settings_routes.py`
- UI route composition, workspace shell, capture report panel, and interaction inventory.
- `docs/generated/openapi-v1.json`

## Verification

- Full pytest suite: **573 passed, 19 skipped**.
- Ruff check: passed.
- Ruff format check: passed.
- BasedPyright: passed with zero errors, warnings, or notes.
- Import-linter: **7 contracts kept, 0 broken**.
- Asset build and drift check: passed.
- Phase 24 focused workflow suite: passed.
- Existing Phase 12, 15, 16, 21, 22, and 23 focused suites: passed.

## Known limitations

- Protocol target allowlist configuration is intentionally not invented in Phase 24. The
  runtime provider accepts an explicit allowlist at composition time; the default
  production graph refuses protocol targets until that policy is supplied.
- Browser Playwright acceptance remains opt-in under the repository's Phase 21–23
  environment gate and is part of Phase 25 qualification.
- Byte-exact/mock-peer replay, plugin installation over API, authentication/RBAC, and
  capability enforcement remain deferred by the accepted ADRs.

## Follow-up recommendations

- Define and approve the configuration contract for protocol replay target allowlists
  before enabling protocol writes in a deployment.
- Execute Phase 25 browser, accessibility, cross-browser, resilience, and packaging
  qualification against the completed workflow views.
