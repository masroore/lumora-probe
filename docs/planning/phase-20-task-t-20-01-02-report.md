# Phase 20 Task T-20-01-02 — dcm4che Suite

**Status:** Complete  
**Date:** 2026-07-31  
**Work package:** WP-20-01 — Interoperability

## Completed work

- Replaced the unavailable dcm4che 5.34.1 image reference with dcm4che 5.33.1 pinned
  by immutable image digest.
- Added an opt-in, real-container dcm4che suite covering:
  - successful C-ECHO through the Lumora relay to the DCMTK SCP;
  - successful C-STORE through the relay using the committed synthetic fixture;
  - calling-AE rejection with dcm4che's association-rejection reason asserted;
  - a valid association immediately after rejection, proving relay recovery.
- Extended scheduled CI startup to wait for both DCMTK and dcm4che services.
- Updated the interoperability runbook with the dcm4che scope and command.

## Design decisions

- dcm4che drives Lumora's downstream relay leg with `storescu`; the relay drives the
  external DCMTK SCP. This keeps the implementation under test outside the Python process
  while exercising both relay legs.
- dcm4che's `storescu` performs C-ECHO when no input file is supplied; the same command
  performs C-STORE when given the synthetic instance path.
- The full modality and transfer-syntax matrix remains owned by `T-20-01-04`.
- Test data remains generated synthetic data. No clinical or de-identified data was added.

## Files added

- `tests/interop/test_dcm4che.py`
- `docs/planning/phase-20-task-t-20-01-02-report.md`

## Files modified

- `tests/interop/docker-compose.yml`
- `tests/interop/README.md`
- `.github/workflows/ci.yml`

## Tests added

- `test_dcm4che_storescu_verifies_lumora_relay`
- `test_dcm4che_storescu_sends_synthetic_instance_through_relay`
- `test_dcm4che_calling_ae_rejection_is_explicit_and_relay_recovers`

## Verification

| Gate | Result |
|---|---|
| dcm4che interoperability suite | `3 passed` |
| Default-gate exclusion | `3 skipped` without `LUMORA_INTEROP=1` |
| DCMTK interoperability suite | `3 passed` |
| Compose readiness | DCMTK and dcm4che healthy |
| Full test suite | `496 passed, 9 skipped` |
| Ruff, import-linter, basedpyright, assets | Pass |

## Known limitations and follow-up

- Orthanc scenarios remain `T-20-01-03`.
- Broader modality and transfer-syntax coverage remains `T-20-01-04`.
- Cross-implementation results publication and failure triage remain `T-20-01-05`.
