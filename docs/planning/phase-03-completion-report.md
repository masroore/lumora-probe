# Phase 03 Completion Report — Development Infrastructure

**Date:** 2026-07-29
**Status:** Complete

## Completed work

- Replaced the legacy CI workflow with locked `uv` setup on push, pull request, schedule,
  and manual dispatch.
- Activated formatting, Ruff linting, import-linter architecture checks, BasedPyright
  checks for `core` and `shared`, tests, per-slice coverage reporting, and dependency
  auditing.
- Added pytest-asyncio, pytest-cov, BasedPyright, and pip-audit as development-only
  dependencies.
- Registered the `unit`, `component`, `dicom`, `e2e`, `interop`, and `slow` marker
  taxonomy and added shared `repository_root` fixture infrastructure.
- Added `scripts/generate_fixtures.py` and a generated three-instance synthetic study.
- Added the non-gating DCMTK, dcm4che, and Orthanc interoperability compose skeleton and
  scheduled/manual CI job.
- Added a byte-comparable golden `.lpcap` harness with path containment checks.
- Ran the pynetdicom threading spike and documented its result.
- Recorded provisional event, protocol-trace, ring-buffer, and UI budgets for Phase 11
  ratification.

## Design decisions

- CI uses `uv sync --locked`; dependency installation is reproducible from `uv.lock`.
- External interoperability runs only on scheduled or manual workflows and is explicitly
  non-gating, while the normal quality job remains strict.
- Security scanning audits an exported, project-free locked requirements file so the
  local editable distribution is not treated as an external PyPI package.
- The pynetdicom result confirms ADR-0002: `EVT_C_STORE` executes on an association thread
  and must cross into the loop through a thread-safe ingress.
- Provisional budgets are recorded separately from baseline architecture documents and
  remain subject to Phase 11 ratification.

## Files added or modified

- `.github/workflows/ci.yml`
- `pyproject.toml`, `uv.lock`
- `scripts/generate_fixtures.py`
- `scripts/spikes/pynetdicom_threading.py`
- `tests/conftest.py`, `tests/test_fixture_generator.py`, `tests/test_golden_harness.py`,
  `tests/test_interop.py`, `tests/test_threading_spike.py`
- `tests/golden/`, `tests/interop/`, `tests/fixtures/dicom/`
- `tests/golden/harness.py`
- `docs/spikes/pynetdicom-threading.md`
- `docs/planning/provisional-non-functional-budgets.md`
- this report

## Verification

- `uv sync --locked`: passed.
- Ruff check and format check: passed.
- BasedPyright on `core` and `shared`: passed with 0 errors, warnings, or notes.
- Full test suite: passed.
- Import-linter: 6 contracts kept, 0 broken.
- Synthetic fixture generation and DICOM readback: passed.
- Threading spike: passed; `EVT_C_STORE` ran off the caller thread.
- Dependency audit in a clean seeded audit environment: passed with no known
  vulnerabilities.
- Package build: passed.

## Known limitations

- Interoperability scenarios are scaffolded but not yet implemented; they remain
  scheduled, non-gating work.
- Coverage has no global threshold by design. Phase 05+ will add component-specific
  thresholds for critical behavior.
- Budgets are provisional until Phase 11 measurement and ratification.

## Follow-up

Proceed to Phase 04 only after review of this report. Do not implement Phase 04 behavior
as part of Phase 03.
