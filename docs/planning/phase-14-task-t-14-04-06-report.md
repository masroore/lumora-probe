# Phase 14 Task Report — T-14-04-06 timeouts and retries

**Status:** Complete

## Completed

- Added `TimeoutRetryRule` with deterministic grouping by association-pair ID, association ID, or
  event correlation ID.
- Recognizes timeout/retry event names and explicit payload markers.
- Emits one finding only when both timeout and retry evidence occur within the same pair.
- Cites all contributing event sequences in sorted order and recommends comparing intervals,
  retry policy, and per-leg evidence.

## Verification

- Seed rule tests: **12 passed**.
- Ruff lint and format: passed.
- BasedPyright on the bundled rules: **0 errors, 0 warnings, 0 notes**.

## Next task

Proceed to T-14-04-07, oversized dataset detection with a configurable threshold.
