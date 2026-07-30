# Phase 14 Task Report — T-14-04-02 no acceptable presentation context

**Status:** Complete

## Completed

- Added `NoAcceptablePresentationContextRule` to the bundled rule set.
- Emits a certain finding only for an observed association rejection with explicitly empty
  accepted contexts and a known SOP class.
- Names the SOP class and offered presentation contexts, including transfer syntaxes when
  supplied.
- Provides concrete remediation to offer a peer-accepted presentation context.
- Avoids inference when accepted-context or SOP-class evidence is absent.

## Verification

- Seed rule tests: **4 passed**.
- Ruff lint and format: passed.
- BasedPyright on the bundled rules: **0 errors, 0 warnings, 0 notes**.

## Next task

Proceed to T-14-04-03, transfer syntax mismatch.
