# Phase 14 Task Report — T-14-02-02 deterministic condition detection

**Status:** Complete

## Completed

- Added `ConditionObservation`, preserving source event ID, source `sequence`, aggregate ID,
  normalized message, and observed details.
- Added `ConditionDetector` as a pure, deterministic analyzer over immutable `EventEnvelope` values.
- Maps mechanically observed association facts to stable condition codes:
  - rejected association with no accepted contexts → `LP-NEG-004`;
  - rejected association with accepted contexts → `LP-NEG-001`;
  - aborted association → `LP-NEG-002`.
- Normalizes explicit registered `code`/`condition_code` payloads from `WarningRaised` and
  `ErrorRaised` without inventing a condition.
- Produces `WarningRaised`/`ErrorRaised`-shaped observations with a mandatory `code` in the
  normalized payload.
- Excludes `origin=client-asserted` events and suppresses duplicate delivery by source event ID.
- Kept event inputs immutable; no finding or inference is written to the evidence stream.

## Tests

- Added three detector tests covering observed rejection, explicit code normalization and
  duplicate delivery, and client-asserted/unknown-code exclusion.
- Full suite: **407 passed, 2 skipped**.

## Verification

- Ruff lint: passed.
- Ruff format: passed.
- BasedPyright on `core`, `shared`, and new analysis modules: 0 errors, 0 warnings, 0 notes.
- Import-linter: 7 kept, 0 broken.

## Next task

Proceed to T-14-02-03, the condition catalogue documentation, before findings rules are added.
