# Phase 14 Task Report — T-14-04-04 slow C-STORE with per-leg attribution

**Status:** Complete

## Completed

- Added configurable `SlowCStoreRule` with a positive nanosecond threshold.
- Reads explicit duration fields or derives duration from observed monotonic summary bounds.
- Requires an explicit leg label and cites the C-STORE event sequence.
- Reports delay on the downstream, Probe-hop, or upstream leg without asserting an end-to-end
  modality-to-PACS measurement.
- Uses `likely` confidence because the threshold establishes a mechanical delay observation, not
  a causal failure diagnosis.

## Verification

- Seed rule tests: **8 passed**.
- Ruff lint and format: passed.
- BasedPyright on the bundled rules: **0 errors, 0 warnings, 0 notes**.

## Next task

Proceed to T-14-04-05, incomplete studies and missing instances.
