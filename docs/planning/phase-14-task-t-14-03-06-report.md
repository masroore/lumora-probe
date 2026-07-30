# Phase 14 Task Report — T-14-03-06 purity guarantee

**Status:** Complete

## Completed

- Added an end-to-end purity test over `RuleEngine` and `AnalysisRepository`.
- Deletes `analysis/`, reruns the same rule set against unchanged events, and asserts byte-identical
  `findings.json` output.
- Asserts `events.jsonl` remains byte-identical and is never used as analysis output.
- Demonstrates a newer rule set can add findings against unchanged evidence while preserving the
  source event sequence.

## Verification

- Phase 14 focused suite: **23 passed**.
- Ruff lint and format: passed.
- BasedPyright on analysis modules: 0 errors, 0 warnings, 0 notes.
- Import-linter: 7 kept, 0 broken.

## Next task

Proceed to T-14-03-07, evidence linking in the UI, using finding cited sequences to resolve real
captured events.
