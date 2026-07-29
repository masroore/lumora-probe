# Phase 12 Task Report — T-12-01-05 Refuse Unreplayable Promoted Windows

**Date:** 2026-07-29
**Status:** Complete

## Completed work

- Protocol replay now accepts promotion completeness metadata at its boundary.
- Any `partial` capture is refused before timing or network work begins.
- Refusal names incomplete aggregates when the manifest provides them and directs operators to
  promote a complete association negotiation.
- Added an adversarial test proving no sender call occurs for a partial window.

## Design decisions

- Refusal is conservative: a partial promoted window is not approximated even if object bytes are
  present. This prevents a successful C-STORE from being misread as faithful association replay.
- The service does not inspect capture internals; callers pass `partial` and
  `incomplete_aggregates` from the manifest contract.

## Files added

- `docs/planning/phase-12-task-t-12-01-05-report.md`

## Files modified

- `src/lumora_probe/replay/service.py`
- `tests/test_phase12_replay_protocol.py`

## Verification

- Targeted replay tests: passed (`10 passed`).
- Ruff lint and format checks: passed.
- Full quality gates remain to run after this task commit.
