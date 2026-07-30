# Phase 12 Remediation Report — Acceptance Blockers

**Date:** 2026-07-30
**Status:** Complete

## Scope

Closed the blockers identified during the Phase 12 acceptance review without adding a replay HTTP
write route or changing the deferred fidelity scope.

## Completed work

- Added `ReplayRuntime` as the application composition seam for protocol replay.
- Bound replay execution to `InMemoryJobRegistry` with durable `app.db` job records, progress
  checkpoints, cooperative cancellation, and operation IDs reused as replay IDs.
- Added asynchronous replay audit persistence through the application database. Audit records are
  buffered at the synchronous service boundary and written off the event loop.
- Added shared application-level protocol replay exclusivity owned by `ReplayRuntime`.
- Added `startup_sweep()` to the job registry and invoked it from the ASGI lifespan so durable
  running jobs become `interrupted` after restart and are never resumed.
- Extended the golden capture with canonical `findings.json` bytes and asserted event-stream and
  finding-set determinism together. The fixture's finding set is intentionally empty; Phase 14
  owns finding generation.

## Files added

- `tests/test_phase12_runtime.py`
- `docs/planning/phase-12-remediation-report.md`

## Files modified

- `src/lumora_probe/core/operations.py`
- `src/lumora_probe/replay/contracts.py`
- `src/lumora_probe/replay/service.py`
- `src/lumora_probe/web/api.py`
- `tests/test_phase12_golden.py`
- `tests/golden/phase12-protocol.lpcap`
- `docs/planning/phase-12-acceptance-report.md`
- `docs/planning/phase-12-completion-report.md`

## Verification

- Focused remediation tests: `11 passed`.
- Full suite: `337 passed, 1 skipped`.
- Ruff lint and format: passed.
- Import-linter: `7 kept, 0 broken`.
- BasedPyright (`core`, `shared`): `0 errors`.
- Package build: sdist and wheel passed.

## Remaining explicit seam

The runtime requires a sender factory and verified `ProtocolReplayDataset` input supplied by the
application composition layer. It does not import capture or association internals, preserving the
slice boundary and the ADR-0005 refusal of byte-exact/mock-peer replay.
