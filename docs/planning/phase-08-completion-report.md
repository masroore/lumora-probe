# Phase 08 Completion Report — REST API

**Date:** 2026-07-29
**Status:** Complete

## Completed work

- Added FastAPI application factory and canonical `/api/v1` router.
- Added structured HTTP error responses mapped from `LumoraError`, route failures, and
  request-validation failures. Responses include status, code, message, remediation,
  context, and correlation ID.
- Added shared pagination, filtering, and stable multi-key sorting policies with explicit
  defaults (`page=1`, `page_size=50`) and maximum page size (`500`).
- Added resource adapters for:
  - captures (list, retrieve, delete)
  - studies, series, and instances (projection-backed list/retrieve contracts)
  - association pairs with separate per-leg data preserved
  - standing events queryable by correlation ID and sequence
  - long-running operation progress
  - settings with source and locked-field metadata
  - combined health, liveness, and readiness
- Added a durable SQLite operation audit registry over the authoritative `app.db` jobs
  table, including progress updates and startup interruption transitions.
- Added one security middleware seam for:
  - server-wide read-only enforcement
  - Host allowlist validation
  - `Origin` and `Sec-Fetch-Site` checks for state-changing requests
  - empty-by-default trusted-proxy behavior
  - no `Access-Control-Allow-Origin` response header
- Added dedicated, rate-limited client-asserted Viewer event endpoint. The endpoint
  forces `producer=web-ui`, forces `origin=client-asserted`, validates the event registry,
  and rejects non-Viewer events.
- Added `lumora` CLI:
  - live `health`
  - live `captures list`
  - offline `capture inspect PATH` for directories and `.lpcap` archives
- Added deterministic OpenAPI generation and the published artifact at
  `docs/generated/openapi-v1.json`.
- Added CLI command surface specification at
  `docs/planning/phase-08-cli-command-surface.md`.

## Design decisions

- Web routes depend on narrow provider protocols instead of importing slice repositories;
  this preserves the existing import-linter boundaries and keeps presentation logic free
  of domain/storage coupling.
- Resource providers are injectable. The default app assembly uses deterministic empty
  providers; runtime composition can supply storage, bus, settings, and operation
  implementations without changing the HTTP contract.
- Error and security responses use an opaque correlation token generated at the HTTP
  boundary. Event identity generation remains injected through core/shared protocols,
  preserving the non-core time/UUID import boundary.
- The CLI uses the live REST surface for live state and reads capture manifests directly
  only for the explicitly offline inspection command.
- No authentication was added, in accordance with ADR-0009. Network exposure remains
  governed by the existing startup gate and the REST host/origin mitigations implement
  ADR-0010.

## Files added

- `src/lumora_probe/web/pagination.py`
- `src/lumora_probe/web/query.py`
- `src/lumora_probe/web/resources.py`
- `src/lumora_probe/web/capture_routes.py`
- `src/lumora_probe/web/collection_routes.py`
- `src/lumora_probe/web/study_routes.py`
- `src/lumora_probe/web/association_routes.py`
- `src/lumora_probe/web/event_routes.py`
- `src/lumora_probe/web/operation_routes.py`
- `src/lumora_probe/web/settings_routes.py`
- `src/lumora_probe/web/health_routes.py`
- `src/lumora_probe/web/security.py`
- `src/lumora_probe/web/client_event_routes.py`
- `src/lumora_probe/cli.py`
- `src/lumora_probe/core/operations.py`
- `scripts/generate_openapi.py`
- `docs/generated/openapi-v1.json`
- `docs/planning/phase-08-cli-command-surface.md`
- `docs/planning/phase-08-completion-report.md`

## Files modified

- `pyproject.toml` — FastAPI/Uvicorn runtime dependencies, HTTP test dependency,
  and `lumora` entry point.
- `uv.lock` — locked dependency graph.
- `src/lumora_probe/web/api.py` — application assembly, route registration, and handlers.
- `src/lumora_probe/web/contracts.py` — HTTP error contract.
- `tests/test_phase08_*.py` — REST, security, CLI, OpenAPI, operation, and event coverage.

## Tests added

- API prefix and application factory behavior.
- Error mapping, correlation IDs, and validation responses.
- Pagination bounds and metadata.
- Filtering, exact filters, plain-text filters, and multi-key sorting.
- Capture CRUD behavior and filesystem directory deletion.
- Projection resources and association pair preservation.
- Event filtering by correlation and sequence.
- Operation progress and durable interruption audit.
- Settings provenance/locks and health/readiness separation.
- Read-only, Host, Origin, Sec-Fetch-Site, forwarded-header, and no-CORS controls.
- Client-asserted Viewer quarantine and rate limiting.
- Live/offline CLI separation.
- OpenAPI artifact freshness.

## Verification

- Full pytest suite: **272 passed, 1 skipped**.
- Ruff format check: passed.
- Ruff lint: passed.
- BasedPyright for `core`, `shared`, `web`, and CLI: **0 errors, 0 warnings, 0 notes**.
- Import-linter: **7 contracts kept, 0 broken**.
- `npm run check:assets`: passed after installing locked Node dependencies.
- `uv build`: passed for source distribution and wheel.

Existing pydicom/pynetdicom fixture warnings remain unchanged. One integration test had a
transient loopback-port collision on the first full run; the isolated rerun and subsequent
full suite passed.

## Known limitations

- Concrete runtime composition of storage repositories, event bus, settings store, and
  operation registry remains an application bootstrap concern; route contracts are ready
  for those providers.
- WebSocket streaming is Phase 09 work.
- DICOM networking, capture writer lifecycle, ring-buffer promotion, and replay remain
  later phases.
- `npm ci` reports existing frontend dependency audit findings (2 moderate, 6 high); no
  package upgrade was made because dependency versions are governed by the approved
  frontend baseline.

## Follow-up recommendations

Proceed to Phase 09. Reuse the Phase 08 event provider and security policy for both WebSocket
endpoints, preserve the same error/correlation conventions, and regenerate the OpenAPI
artifact whenever REST routes change.
