# Phase 12 Task Report — T-12-01-03 Fidelity Gate

**Date:** 2026-07-29
**Status:** Complete

## Completed work

- Added a protocol replay preflight gate requiring capture fidelity `protocol` or `wire`.
- Refused `events` and `objects` captures before any sleep or sender call.
- Error context identifies the missing `pdus.jsonl` protocol stream and remediation names the
  supported fidelity tiers.
- Added acceptance coverage for both unsupported capture fidelities.

## Design decisions

- The gate accepts the manifest fidelity as a string at the replay service boundary, avoiding an
  import from the captures implementation slice. The capture composition layer passes the
  manifest value through its public contract.
- `wire` is accepted because it includes protocol evidence; protocol replay remains a DICOM SCU
  reconstruction, not byte-exact wire replay.
- This gate does not yet reject partial promoted windows whose negotiation is missing; that is
  T-12-01-05.

## Files added

- `docs/planning/phase-12-task-t-12-01-03-report.md`

## Files modified

- `src/lumora_probe/replay/service.py`
- `tests/test_phase12_replay_protocol.py`

## Verification

- Targeted replay tests: passed (`9 passed`).
- Ruff lint and format checks: passed.
- Full quality gates remain to run after this task commit.

## Known limitations

- Fidelity metadata is supplied by the caller; capture repository composition is not yet a
  replay-owned API.
- Live-write guardrails, provenance, job persistence, exclusivity, and cancellation remain later
  Phase 12 tasks.
