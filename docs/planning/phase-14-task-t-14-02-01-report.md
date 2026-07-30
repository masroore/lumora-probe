# Phase 14 Task Report — T-14-02-01 condition ID registry

**Status:** Complete

## Completed

- Added immutable `ConditionId` validation for the stable `LP-XXX-NNN` form.
- Added `ConditionId.from_parts(namespace, number)` with explicit validation for three uppercase
  namespace letters and sequence numbers `001` through `999`.
- Added immutable `ConditionDefinition` metadata for name, description, and remediation text.
- Added `ConditionIdRegistry` with duplicate/reuse rejection, lookup, required lookup, stable
  lexical ordering, and typed iteration. `ConditionRegistry` remains an alias for readability.
- Re-exported the condition contracts through `analysis/contracts.py`.
- Documented the allocation rule and diagnostic-condition/finding terminology in the glossary.

## Tests

- `tests/test_phase14_analysis.py`: 9 unit tests covering valid IDs, invalid IDs, namespace/number
  allocation, duplicate rejection, stable ordering, lookup, and text normalization.

## Verification

- Ruff lint: passed.
- BasedPyright on the new analysis modules: 0 errors, 0 warnings, 0 notes.
- Import-linter: 7 kept, 0 broken.
- Focused Phase 13 regression plus Phase 14 tests: 19 passed.

## Next task

Proceed to T-14-02-02, deterministic condition detection, using the registry without adding rule
inference to observed event payloads.
