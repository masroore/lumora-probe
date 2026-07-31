# Phase 20 Task T-20-01-01 — DCMTK Suite

**Status:** Complete  
**Date:** 2026-07-31  
**Work package:** WP-20-01 — Interoperability

## Completed work

- Replaced the non-existent DCMTK image reference in the interoperability skeleton with
  DCMTK 3.6.8 pinned by immutable image digest.
- Added an opt-in, real-container DCMTK suite covering:
  - successful C-ECHO through the Lumora relay to the DCMTK SCP;
  - successful C-STORE through the relay using the committed synthetic Explicit VR Little Endian fixture;
  - calling-AE rejection with the protocol reason asserted;
  - a valid association immediately after rejection, proving relay recovery.
- Kept external implementation tests outside the default gate. `LUMORA_INTEROP=1` remains
  required and acts as the explicit acknowledgment for the isolated non-loopback test bind.
- Expanded suite documentation with purpose, scope, prerequisites, expected outcomes, and
  maintenance guidance required by the testing strategy.

## Design decisions

- DCMTK drives Lumora's downstream relay leg while the relay drives the external DCMTK SCP.
  This verifies both relay legs against an implementation outside project control.
- This task uses one baseline transfer syntax only. The complete and exotic transfer-syntax
  matrix remains owned by `T-20-01-04`.
- Test data remains generated synthetic data under the project-owned UID root. No clinical
  or de-identified data was introduced.
- Container-to-host routing defaults to `host.docker.internal` and is configurable through
  `LUMORA_INTEROP_HOST` for platform-specific Docker networking.

## Files added

- `tests/interop/test_dcmtk.py`
- `docs/planning/phase-20-task-t-20-01-01-report.md`

## Files modified

- `tests/interop/docker-compose.yml`
- `tests/interop/README.md`
- `CLAUDE.md`
- `.github/workflows/ci.yml`

## Tests added

- `test_dcmtk_echoscu_verifies_lumora_relay`
- `test_dcmtk_storescu_sends_synthetic_instance_through_relay`
- `test_dcmtk_calling_ae_rejection_is_explicit_and_relay_recovers`

## Verification

| Gate | Result |
|---|---|
| DCMTK interoperability suite | `3 passed` |
| Default-gate exclusion | `3 skipped` without `LUMORA_INTEROP=1` |
| Full test suite | `496 passed, 6 skipped` |
| Ruff lint | Pass |
| Ruff format | Pass |
| Import-linter | 7 contracts kept, 0 broken |
| Basedpyright (`core`, `shared`) | 0 errors, 0 warnings, 0 notes |
| Committed asset check | Pass |

## Known limitations and follow-up

- dcm4che and Orthanc scenarios remain `T-20-01-02` and `T-20-01-03`.
- Broader modality and transfer-syntax coverage remains `T-20-01-04`.
- Cross-implementation results publication and failure triage remain `T-20-01-05`.
