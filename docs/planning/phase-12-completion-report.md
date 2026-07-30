# Phase 12 Completion Report — Replay Engine

**Date:** 2026-07-29
**Status:** Complete

## Completed work

Phase 12 replay engine is implemented across all approved WBS work packages:

- Offline event replay into the loop-owned bus with original/scaled monotonic timing.
- Protocol replay through the Phase 10 SCU transport with encoded dataset parsing off-loop.
- Fidelity gate for `events`/`objects` captures and refusal of partial promoted windows.
- Fresh replay correlation and event identities, `replay_id`, and `replay_of_event_id` provenance.
- Capture-while-replaying through the existing bus `capture_id` seam.
- Dry-run default, explicit target requirement, C-STORE allowlist enforcement, audit sink,
  and single-live-replay exclusivity.
- In-memory asyncio job registry with UUIDv7 identity injection, cooperative cancellation,
  progress checkpoints, durable `app.db` audit integration, interruption sweep, bus progress,
  and per-type concurrency bounds.
- Synthetic committed `.lpcap` fixture and byte-comparable replay regression.

## Design decisions

- Replay services accept explicit immutable input records and public contracts rather than
  importing capture or association implementation modules.
- All timing uses `monotonic_ns`; wall UTC is used only for audit display.
- Protocol replay remains DICOM SCU dataset replay. Byte-exact/mock-peer replay remains deferred
  by ADR-0005.
- Live protocol sends require explicit composition of target, allowlist, and `dry_run=False`.
  No web/API live-write route was added ahead of the guardrails.
- Job progress uses the existing event bus with the new `ReplayProgressed` catalog entry; no
  second progress transport was introduced.

## Files added

- `docs/planning/phase-12-completion-report.md`
- `docs/planning/phase-12-task-t-12-01-01-report.md`
- `docs/planning/phase-12-task-t-12-01-02-report.md`
- `docs/planning/phase-12-task-t-12-01-03-report.md`
- `docs/planning/phase-12-task-t-12-01-04-report.md`
- `docs/planning/phase-12-task-t-12-01-05-report.md`
- `docs/planning/phase-12-task-t-12-02-01-report.md`
- `docs/planning/phase-12-task-t-12-02-02-report.md`
- `docs/planning/phase-12-task-t-12-02-03-report.md`
- `docs/planning/phase-12-task-t-12-03-01-report.md`
- `docs/planning/phase-12-task-t-12-03-02-report.md`
- `docs/planning/phase-12-task-t-12-03-03-report.md`
- `docs/planning/phase-12-task-t-12-03-04-report.md`
- `docs/planning/phase-12-task-t-12-03-05-report.md`
- `docs/planning/phase-12-task-t-12-04-01-report.md`
- `docs/planning/phase-12-task-t-12-04-02-report.md`
- `docs/planning/phase-12-task-t-12-04-03-report.md`
- `docs/planning/phase-12-task-t-12-04-04-report.md`
- `docs/planning/phase-12-task-t-12-04-05-report.md`
- `docs/planning/phase-12-task-t-12-04-06-report.md`
- `docs/planning/phase-12-task-t-12-05-01-report.md`
- `docs/planning/phase-12-task-t-12-05-02-report.md`
- `tests/test_phase12_replay_protocol.py`
- `tests/test_phase12_jobs.py`
- `tests/test_phase12_runtime.py`
- `tests/test_phase12_golden.py`
- `tests/golden/phase12-protocol.lpcap`

## Files modified

- `src/lumora_probe/associations/contracts.py`
- `src/lumora_probe/associations/network.py`
- `src/lumora_probe/replay/contracts.py`
- `src/lumora_probe/replay/service.py`
- `src/lumora_probe/core/operations.py`
- `src/lumora_probe/shared/events.py`
- `src/lumora_probe/core/operations.py`
- `src/lumora_probe/replay/contracts.py`
- `src/lumora_probe/replay/service.py`
- `src/lumora_probe/web/api.py`
- `docs/generated/event-catalog-v1.json`
- `CLAUDE.md`

## Tests added

- Protocol replay ordering, monotonic timing, fidelity refusal, partial-window refusal, dry-run,
  explicit target, allowlist, audit, exclusivity, SCU parsing, and cancellation.
- Event replay provenance and capture routing.
- In-memory job completion, progress, cancellation, interruption, durable checkpoints, bus
  progress, and concurrency bounds.
- Golden capture integrity and byte-comparable event replay.

## Quality gates

- Ruff lint: passed.
- Ruff format check: passed.
- Import-linter: passed (`7 kept`, `0 broken`).
- BasedPyright (`core`, `shared`): passed (`0 errors`).
- Full test suite: passed (`337 passed, 1 skipped`).
- Package build: passed (`uv build`).

## Known limitations

- Protocol replay input assembly from a verified capture package remains an explicit composition seam;
  the replay runtime does not reach into capture repositories.
- Existing SCU transport opens one association per dataset. Association-level reconstruction is
  not claimed; byte-exact/mock-peer replay remains deferred by ADR-0005.
- Durable protocol replay jobs are now composed through `ReplayRuntime`, including async audit
  persistence, restart interruption sweep, shared live-replay exclusivity, cancellation, and
  progress. No new replay HTTP route was added; API exposure belongs to a later approved
  integration task.
- Interoperability suite remains opt-in and was not run by the default quality gate.

## Follow-up recommendations

- Before Phase 13, add the approved application adapter that joins verified capture objects to
  source C-STORE monotonic samples through public capture contracts; `ReplayRuntime` now provides
  the durable execution seam that adapter will call.
- Add live loopback protocol replay coverage against `DICOMListener` once guardrails are wired to
  the runtime composition root.
- Keep Phase 13 blocked until this report and the Phase 12 task reports are accepted.
