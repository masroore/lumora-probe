# Phase 19 — Packaging Completion Report

**Date:** 2026-07-31
**Status:** Implemented; Docker daemon smoke test pending on the development host
**Governing plan:** `docs/planning/02-phase-plan.md` §Phase 19

## Completed work

### WP-19-01 — Distribution

- Renamed the published distribution to `lumora-probe`; retained `probe-lite`,
  `sender-lite`, and `lumora` entry points.
- Added explicit Hatch sdist inclusion for Python sources, committed runtime assets, and
  lock metadata.
- Kept committed `static/` and `assets/vendor/` files in both wheel and sdist.
- Fixed installed-wheel static asset discovery. Source checkout and installed distributions
  now resolve the packaged `static/` directory.
- Added wheel/sdist artifact tests and an offline installation test that runs the CLI with an
  empty `PATH`, no Node, and `uv pip install --no-index --no-deps`.

### Docker image and volume contract

- Added a Python 3.13 slim image with no Node runtime dependency.
- Image creates and runs as non-root user `lumora`.
- Image owns one data volume at `/var/lib/lumora`, sets `LUMORA_DATA_DIR`, exposes HTTP and
  DICOM ports, and starts with the explicit network exposure acknowledgment required by
  ADR-0010.
- Added deployment documentation naming the reverse proxy as the TLS/authentication
  boundary and documenting bind-mount ownership.
- Added Dockerfile and build-context contract tests.

### Upgrade and safety documentation

- Documented `app.db` migration, rebuildable `index.db`, the data-root `version` marker,
  backup targeting, recovery posture, and newer-version refusal.
- Added an explicit newer-data-directory non-mutation test.
- Added a page-load test proving HTML asset references are local and committed; no external
  CDN or remote asset is required.

## Files added

- `.dockerignore`
- `Dockerfile`
- `docs/guides/docker.md`
- `docs/guides/upgrade-and-migration.md`
- `docs/planning/phase-19-completion-report.md`
- `tests/test_phase19_data_version.py`
- `tests/test_phase19_distribution.py`
- `tests/test_phase19_docker.py`
- `tests/test_phase19_no_outbound.py`
- `tests/test_phase19_packaging.py`

## Files modified

- `pyproject.toml`
- `uv.lock`
- `README.md`
- `AGENTS.md`
- `src/lumora_probe/web/workspace_routes.py`
- `docs/guides/deployment-topologies.md`
- `docs/guides/operator-guide.md`
- `docs/probe_lite/README.md`

## Verification

| Gate | Result |
|---|---|
| Full test suite | `496 passed, 3 skipped` |
| Ruff lint | Pass |
| Ruff format check | Pass |
| Import-linter | 7 contracts kept, 0 broken |
| Basedpyright | 0 errors, 0 warnings, 0 notes |
| Committed asset check | Pass |
| Wheel/sdist build | Pass; assets present in both artifacts |
| Offline/no-Node package run | Pass |
| Newer data-directory refusal | Pass |
| Local-only page-load check | Pass |
| Dockerfile contract | Pass |
| Docker image build/run | Not executed: Docker daemon unavailable on host |

## Design decisions

- Distribution metadata now follows Phase 19's public install contract, `lumora-probe`.
  Import paths and existing Lite console scripts remain backward-compatible.
- Runtime assets remain committed and packaged; Node stays an asset-build dependency only,
  per ADR-0025.
- Docker uses explicit `--trust-network --host 0.0.0.0` rather than silently changing the
  application exposure policy. Reverse proxy configuration remains outside the image.
- No schema redesign was introduced. Existing app migration and index projection behavior are
  documented rather than replaced.

## Known limitations and follow-up

- A Docker daemon must be available to run the final image smoke test. The local command was
  attempted and failed before build because all configured Docker endpoints were offline.
  CI or a host with a running daemon must execute:

  ```console
  docker build --pull=false -t lumora-probe:phase19-test .
  docker run --rm -v lumora-data:/var/lib/lumora lumora-probe:phase19-test
  ```

- Phase 20 remains the next approved phase: scheduled interoperability, acceptance
  validation, release notes, and GA sign-off.

## Implementation commits

- `d49618f` — distribution metadata and packaged assets
- `913e1ed` — offline/no-Node installation verification
- `fcb25a2` — local-only page-load verification
- `acba9ee` — newer data-directory refusal verification
- `349c825` — upgrade and migration guide
- `edffa33` — non-root single-volume Docker image
- `95983cc` — installed static asset verification
- `f7bfb67` — distribution reference documentation alignment
