# Phase 04 Completion Report — Core Infrastructure

**Date:** 2026-07-29  
**Status:** Complete

## Completed work

- Added immutable Pydantic Settings startup configuration with precedence:
  environment > `.env` > TOML/YAML > defaults.
- Added configuration provenance for every startup setting and structured validation
  failures naming the setting and source.
- Added OS-conventional `LUMORA_DATA_DIR` resolution, independently relocatable capture
  roots, additional read-only capture roots, UUIDv7 capture path containment, data-directory
  version markers, and network-filesystem refusal for SQLite paths.
- Added structured core errors with stable `LUMORA-CORE-*` codes, context, and remediation.
- Added structlog setup with correlation context and recursive sensitive-field redaction.
- Added the heterogeneous `Service` lifecycle protocol, ordered startup, reverse shutdown,
  draining hooks, bounded shutdown grace period, executor pool, and per-service health.
- Added readiness/liveness aggregation through `HealthRegistry`.
- Added runtime `settings.toml` storage separate from the rebuildable index, with default/file/
  environment/runtime provenance, atomic writes, source-lock refusal, and restart-required
  errors.
- Added Tailwind CSS 4 build output, vendored HTMX/Alpine/Chart.js/Tabulator assets, and a
  committed Cornerstone3D rendering-only bundle.
- Added asset provenance manifest, deterministic asset build/check scripts, committed outputs,
  wheel force-inclusion, and CI stale-asset enforcement.
- Recorded the Cornerstone3D bundling spike result and preserved server-side DICOM parsing and
  codec responsibilities per ADR-0015.

## Design decisions

- Startup settings use `pydantic-settings`'s `BaseSettings` boundary while resolving sources
  explicitly so source provenance and error messages remain deterministic.
- Runtime settings are persisted in `settings.toml` under the data root, never in `index.db`.
- SQLite safety checks reject only network-backed database paths; evidence capture roots may be
  relocated to network storage as allowed by ADR-0011.
- Node packages are `devDependencies` because Node is required only to rebuild committed assets;
  installed Lumora Probe runtime has no Node requirement.
- The Cornerstone bundle imports only rendering APIs. No browser DICOM parser or WASM codec is
  included.

## Files added

- `src/lumora_probe/core/config.py`
- `src/lumora_probe/core/errors.py`
- `src/lumora_probe/core/health.py`
- `src/lumora_probe/core/lifecycle.py`
- `src/lumora_probe/core/logging.py`
- `src/lumora_probe/core/paths.py`
- `src/lumora_probe/settings/runtime.py`
- `tests/test_core_infrastructure.py`
- `tests/test_asset_pipeline.py`
- `package.json`, `package-lock.json`
- `assets/source/app.css`, `assets/source/cornerstone-renderer.js`
- `assets/vendor/*`
- `static/css/app.css`, `static/js/cornerstone-renderer.js`
- `scripts/build-assets.mjs`, `scripts/check-assets.py`
- `docs/spikes/cornerstone3d-bundling.md`

## Files modified

- `pyproject.toml`, `uv.lock`
- `.github/workflows/ci.yml`

## Tests and verification

- Full pytest suite: **198 passed, 1 skipped**.
- Phase 04 component tests: **13 passed**.
- Asset tests: **2 passed**.
- Ruff lint: passed.
- Ruff format check: passed.
- BasedPyright strict checks for `core` and `shared`: passed with 0 errors, warnings, or notes.
- Import-linter: 6 contracts kept, 0 broken.
- Package build: passed; wheel contains committed `static/` and `assets/vendor/` outputs.
- `npm ci`, asset build, and committed-output drift check: passed.
- `npm audit --omit=dev --audit-level=high`: 0 runtime vulnerabilities.
- Verified path traversal rejection, non-loopback bind refusal, config-source validation,
  network filesystem refusal, newer data-directory refusal, runtime setting source locking,
  lifecycle draining, and executor offload.

## Known limitations

- YAML startup parsing intentionally supports flat scalar/list settings only; TOML is the
  preferred full-fidelity configuration format.
- The asset pipeline provides the rendering bundle and vendored libraries; viewer integration,
  custom image loading, and server decode are Phase 13 work.
- `npm audit` reports vulnerabilities in transitive build-only packages when auditing dev
  dependencies; runtime asset installation is unaffected because generated assets are committed.
- Network filesystem detection is conservative and based on platform mount metadata; unusual
  enterprise filesystem drivers may require a later platform-specific detector.

## Follow-up

Proceed to Phase 05 only after this report is reviewed. Phase 05 must add the injected `Clock`
and `IdGenerator` protocols and domain invariants before downstream application behavior is
implemented.
