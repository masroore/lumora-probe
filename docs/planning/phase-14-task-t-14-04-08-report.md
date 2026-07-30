# Phase 14 Task Report — T-14-04-08 C-MOVE out-of-band finding

**Status:** Complete

## Completed

- Added `CMoveOutOfBandRule` for observed `CMoveRequested` events.
- States that C-MOVE sub-operation C-STORE traffic flows to the configured destination outside
  Probe's capture path.
- Names the destination AE when available and cites the request event sequence.
- Provides the ADR-0024 remediation: point the destination AE at Probe or use C-GET.
- Added `bundled_rules()` to construct all eight seed rule families with configurable slow-C-STORE
  and oversized-dataset thresholds.

## Verification

- Seed rule tests: **16 passed**.
- Ruff lint and format: passed.
- BasedPyright on the bundled rules: **0 errors, 0 warnings, 0 notes**.
- Import-linter: **7 kept, 0 broken**.

## Next task

Proceed to Phase 14 completion report and acceptance verification.
