# Phase 14 Task Report — T-14-03-02 coarse confidence levels

**Status:** Complete

## Completed

- `FindingConfidence` restricts findings to `certain`, `likely`, and `possible`.
- Numeric scores, percentages, arbitrary labels, and calibrated-looking precision are rejected.
- Serialized findings expose the stable lowercase vocabulary for reports and UI consumers.
- Confidence is carried with every finding and remains distinct from observed condition severity.

## Verification

- Confidence acceptance/rejection tests are part of `tests/test_phase14_analysis.py`.
- Phase 14 focused suite: **18 passed**.
- Full suite after the finding-model implementation: **413 passed, 2 skipped**.
- Ruff, BasedPyright, and import-linter gates passed.

## Next task

Proceed to T-14-03-03, analysis persistence. Findings must be written inside the capture's
`analysis/` directory and never appended to `events.jsonl`.
