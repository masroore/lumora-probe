# Phase 12 Task Report — T-12-01-02 Protocol Replay

**Date:** 2026-07-29
**Status:** Complete

## Completed work

- Added a structural async DICOM dataset sender contract through the associations public
  boundary.
- Added `DICOMSCUClient.send_dataset()`, which parses captured bytes off the event loop,
  derives the SOP Class UID, and delegates to the existing C-STORE transport.
- Added `ProtocolReplayDataset` and `ProtocolReplayResult` contracts.
- Added `ProtocolReplayService` with preflight monotonic ordering validation, injected timing,
  scaled timing, ordered C-STORE submission, and per-dataset success/failure accounting.
- Added deterministic protocol replay tests, including SCU byte parsing with a synthetic DICOM
  dataset.

## Design decisions

- Protocol replay accepts an explicit immutable replay input record containing encoded bytes,
  transfer syntax, and the captured monotonic timestamp. The capture composition layer can
  construct these records from a verified `CapturePackage` without allowing the replay slice to
  import capture internals.
- The SCU transport opens and releases an association per dataset through the existing
  `DICOMSCUClient.store_dataset()` path. Captured-association grouping is not inferred from
  object order; a future task must define that policy before claiming wire-level fidelity.
- Parsing and network work stay off the asyncio loop. Protocol replay has no API, job, audit,
  target allowlist, dry-run, fidelity refusal, or provenance path yet; those remain their
  assigned Phase 12 tasks and must be present before exposing live writes.

## Files added

- `tests/test_phase12_replay_protocol.py`
- `docs/planning/phase-12-task-t-12-01-02-report.md`

## Files modified

- `src/lumora_probe/associations/contracts.py`
- `src/lumora_probe/associations/network.py`
- `src/lumora_probe/replay/contracts.py`
- `src/lumora_probe/replay/service.py`

## Verification

- Targeted protocol replay tests: passed (`7 passed`, including event replay regression).
- Ruff lint and format checks: passed.
- Import-linter architecture contracts: passed (`7 kept`).
- BasedPyright checks for `core` and `shared`: passed (`0 errors`).
- Full test suite: passed (`317 passed, 1 skipped`).
- Package build: passed (`uv build`).

## Known limitations

- Replay input assembly from capture objects and source timing is not exposed as a public API;
  callers must supply explicit `ProtocolReplayDataset` records.
- One-association-per-dataset behavior follows the existing Phase 10 SCU primitive and is not
  a claim of captured-association reconstruction.
- Fidelity refusal, live-write guardrails, provenance, jobs, cancellation, and golden capture
  regression remain later Phase 12 tasks.
