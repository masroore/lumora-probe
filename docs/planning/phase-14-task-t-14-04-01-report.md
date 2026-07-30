# Phase 14 Task Report — T-14-04-01 rejected association rules

**Status:** Complete

## Completed

- Added the bundled rule-set version constant and `RejectedAssociationRule`.
- Emits a `certain` finding only when one observed `AssociationRejected` event contains the
  complete result/source/reason triplet.
- Cites the rejection event's sequence and gives a concrete peer-log remediation step.
- Skips incomplete payloads instead of inferring missing values.

## Verification

- Seed rule tests: **2 passed**.
- Ruff lint and format: passed.
- BasedPyright on the new rule module: **0 errors, 0 warnings, 0 notes**.
- Import-linter: **7 kept, 0 broken**.

## Next task

Proceed to T-14-04-02, no acceptable presentation context.
