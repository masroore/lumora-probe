# Phase 14 Task Report — T-14-04-05 incomplete studies and missing instances

**Status:** Complete

## Completed

- Added `IncompleteStudyRule` for study summary/projection evidence.
- Detects missing instances from explicit missing lists, expected-vs-observed counts, or instance
  set differences.
- Reports the study identity and missing count with `likely` confidence.
- Deliberately describes the missing-instance problem under investigation without asserting its
  cause or assigning blame to a specific leg.
- Provides next steps to compare sender, association, and capture boundaries.

## Verification

- Seed rule tests: **10 passed**.
- Ruff lint and format: passed.
- BasedPyright on the bundled rules: **0 errors, 0 warnings, 0 notes**.

## Next task

Proceed to T-14-04-06, timeout and retry pattern detection.
