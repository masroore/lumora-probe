# Phase 12 Task Report — T-12-01-01 Event Replay

**Date:** 2026-07-29
**Status:** Complete

## Completed work

- Added an asynchronous event replay service that publishes persisted `EventEnvelope`
  instances directly into the loop-owned event bus.
- Preserved event payloads and persisted input order; the bus remains the ordering
  authority and assigns the replay stream's sequence values.
- Added original and scaled timing using `monotonic_ns` deltas only. Wall-clock values
  are not used for replay delays.
- Added preflight validation for replay speed and non-monotonic source streams so an
  invalid stream fails before any event is published.
- Added an immutable replay result contract with published-event count and access to the
  sequenced envelopes.

## Design decisions

- The service accepts an iterable of already-decoded envelopes instead of importing the
  captures slice internals. Composition code can adapt any capture reader through this
  contract without violating ADR-0012 slice boundaries.
- `speed=1.0` means original timing. Values greater than one accelerate replay; values
  between zero and one slow it down.
- The service has no DICOM or network dependency. Protocol replay, provenance, fidelity
  gates, jobs, and persisted-capture composition remain later Phase 12 tasks.

## Files added

- `src/lumora_probe/replay/contracts.py`
- `src/lumora_probe/replay/service.py`
- `tests/test_phase12_replay.py`
- `docs/planning/phase-12-task-t-12-01-01-report.md`

## Verification

- Phase 12 replay tests: passed (`4 passed`).
- Ruff lint and format checks: passed.
- Import-linter architecture contracts: passed (`7 kept`).
- BasedPyright checks for `core` and `shared`: passed (`0 errors`).
- Full test suite: passed (`314 passed, 1 skipped`).
- Package build: passed (`uv build`).

## Known limitations

- Protocol replay and live-write guardrails are not implemented by this task.
- Replay provenance (`replay_id`, `replay_of_event_id`, and fresh correlation IDs) is
  deferred to T-12-02-01 and T-12-02-02.
- Capture-package loading and golden `.lpcap` regression coverage remain later Phase 12
  tasks.
