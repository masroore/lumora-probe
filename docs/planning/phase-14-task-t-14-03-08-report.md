# Phase 14 Task Report — T-14-03-08 client-asserted exclusion hardening

**Status:** Complete

## Completed

- Centralized analysis admission in `_observed_events()`.
- Applied the admission filter before both condition detection and rule evaluation.
- Kept client-asserted events out of every `RuleContext`, preventing them from supplying
  inference inputs or timing-like monotonic gaps to rules.
- Added an adversarial test with a client event carrying a condition code, a later sequence,
  and an extreme monotonic value; the analysis context contains only the observed event.

## Verification

- Phase 14 focused suite: **26 passed**.
- Ruff lint and format: passed.
- BasedPyright on the changed analysis service: **0 errors, 0 warnings, 0 notes**.
- Import-linter: **7 kept, 0 broken**.

## Next task

Proceed to the Phase 14 seed rule set, beginning with T-14-04-01, rejected association rules.
