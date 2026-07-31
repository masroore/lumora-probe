# Phase 20 Task T-20-01-03 — Orthanc Suite

**Status:** Complete  
**Date:** 2026-07-31  
**Work package:** WP-20-01 — Interoperability

## Completed work

- Pinned Orthanc 24.5.1 by immutable image digest and restricted the host DICOM
  publication to loopback (`127.0.0.1:4242`).
- Added an opt-in, real-container Orthanc suite covering:
  - successful C-ECHO through the Lumora relay to Orthanc's DICOM SCP;
  - successful C-STORE through the relay using a committed synthetic fixture;
  - calling-AE rejection with the protocol rejection asserted;
  - a valid association immediately after rejection, proving relay recovery.
- Extended scheduled CI startup to wait for the Orthanc service.
- Updated the interoperability runbook to include Orthanc and the full three-service
  invocation.

## Design decisions

- DCMTK drives the downstream relay leg while the relay drives Orthanc's DICOM SCP.
  This tests Orthanc as the external implementation under the current task boundary.
- Orthanc's DICOM service is the tested interface; no REST-only upload shortcut is used.
- The full modality and transfer-syntax matrix remains owned by `T-20-01-04`.
- Test data remains generated synthetic data. No clinical or de-identified data was added.

## Files added

- `tests/interop/test_orthanc.py`
- `docs/planning/phase-20-task-t-20-01-03-report.md`

## Files modified

- `tests/interop/docker-compose.yml`
- `tests/interop/README.md`
- `.github/workflows/ci.yml`

## Tests added

- `test_dcmtk_echoscu_verifies_orthanc_through_lumora_relay`
- `test_dcmtk_storescu_sends_synthetic_instance_to_orthanc_through_relay`
- `test_dcmtk_calling_ae_rejection_is_explicit_and_orthanc_relay_recovers`

## Verification

| Gate | Result |
|---|---|
| Orthanc interoperability suite | `3 passed` |
| Compose readiness | DCMTK and Orthanc healthy |
| Default-gate exclusion | `3 skipped` without `LUMORA_INTEROP=1` |
| Full test suite | `496 passed, 12 skipped` |
| Ruff, import-linter, basedpyright, assets | Pass |

## Known limitations and follow-up

- Broader modality and transfer-syntax coverage remains `T-20-01-04`.
- Cross-implementation results publication and failure triage remain `T-20-01-05`.
