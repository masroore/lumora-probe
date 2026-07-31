# Phase 20 Task T-20-01-04 — Transfer-Syntax Matrix

**Status:** Complete  
**Date:** 2026-07-31  
**Work package:** WP-20-01 — Interoperability

## Completed work

- Added a scheduled, opt-in transfer-syntax matrix over real dcm4che, DCMTK, and
  Orthanc containers.
- Generates compressed synthetic instances with DCMTK tools and sends them through
  Lumora with dcm4che's exact `--store-tc` negotiation.
- Covers:
  - Explicit VR Little Endian;
  - RLE Lossless;
  - JPEG Lossless SV1;
  - JPEG Baseline;
  - JPEG-LS Lossless.
- Asserts file metadata transfer syntax before transmission and a successful C-STORE
  response after the relay reaches Orthanc.
- Added a shared Compose volume for generated synthetic matrix objects.

## Design decisions

- Orthanc is the matrix upstream because it accepts the compressed transfer syntaxes
  used by this release matrix; DCMTK remains the deterministic encoder and dcm4che
  provides exact single-transfer-syntax negotiation.
- Matrix coverage is positive-path only. Positive and negative association behavior is
  covered by each implementation suite; cross-implementation failures remain visible
  to the publication/triage task.
- JPEG 2000, MPEG, HEVC, and other syntaxes not supported by the pinned DCMTK encoder
  image remain outside this task and require a future encoder/toolchain decision.
- Fixtures remain synthetic-only. No clinical or de-identified data was added.

## Files added

- `tests/interop/test_transfer_syntax_matrix.py`
- `docs/planning/phase-20-task-t-20-01-04-report.md`

## Files modified

- `tests/interop/docker-compose.yml`
- `tests/interop/README.md`

## Tests added

- `test_transfer_syntax_reaches_upstream_unchanged` with five parametrized transfer
  syntax cases.

## Verification

| Gate | Result |
|---|---|
| Full interop suites | `14 passed` |
| Transfer-syntax matrix | `5 passed` |
| Compose readiness | DCMTK, dcm4che, and Orthanc healthy |
| Default-gate exclusion | Matrix skipped without `LUMORA_INTEROP=1` |

## Known limitations and follow-up

- Results publication and failure triage remain `T-20-01-05`.
- Additional exotic syntax encoders require explicit image/toolchain support.
