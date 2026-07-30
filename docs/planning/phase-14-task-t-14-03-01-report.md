# Phase 14 Task Report — T-14-03-01 finding model

**Status:** Complete

## Completed

- Added immutable `Finding` model with rule ID, rule-set version, coarse confidence, cited event
  sequence numbers, explanation, and next steps.
- Added `FindingConfidence` with only `certain`, `likely`, and `possible`; numeric confidence is
  rejected to prevent invented precision.
- Required at least one cited sequence and enforce sorted, unique, non-negative evidence links.
- Added stable JSON serialization for report and UI consumers.
- Kept finding data separate from observed `ConditionObservation` data; persistence and rule
  evaluation remain later tasks.

## Tests

- Added tests for serialization, confidence vocabulary, evidence-link invariants, and remediation
  step validation.
- Phase 14 focused suite: **18 passed**.

## Verification

- Ruff lint and format: passed.
- BasedPyright on new analysis modules: 0 errors, 0 warnings, 0 notes.
- Import-linter: 7 kept, 0 broken.

## Next task

Proceed to T-14-03-02, the confidence-level contract is implemented here; next add the analysis
persistence boundary without writing findings to `events.jsonl`.
