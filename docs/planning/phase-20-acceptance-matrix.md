# Phase 20 PRD Acceptance Matrix

**Basis:** `docs/architecture-baseline/Lumora-Probe-PRD.md` §26  
**Status:** Demonstrated  
**Date:** 2026-07-31

## Acceptance items

| PRD requirement | Evidence | Result |
|---|---|---|
| Capture DICOM associations | `tests/test_phase10_network.py`, `tests/test_phase11_capture.py`, `tests/interop/test_dcmtk.py` | PASS |
| Persist events | `tests/test_phase06_capture_repository.py`, `tests/test_phase07_events.py`, `tests/test_phase11_capture.py` | PASS |
| Display studies | `tests/test_phase08_studies_api.py`, `tests/test_phase13_studies.py`, `tests/test_phase13_workspace.py` | PASS |
| Render images | `tests/test_phase13_decode.py`, `tests/test_phase13_frame_api.py`, `tests/test_phase13_viewer_e2e.py` | PASS |
| Inspect metadata | `tests/test_phase13_transfer_inspector.py`, `tests/test_phase13_workspace.py` | PASS |
| Replay captures | `tests/test_phase12_replay.py`, `tests/test_phase12_golden.py`, `tests/test_phase12_replay_protocol.py` | PASS |
| Produce reports | `tests/test_phase15_reports.py`, `tests/test_phase15_report_jobs.py`, `tests/test_phase15_handover.py` | PASS |
| Support plugins | `tests/test_phase16_plugin_sdk.py`, `tests/test_phase16_plugin_management.py`, `tests/test_phase16_bundled_plugins.py` | PASS |
| Expose REST API | `tests/test_phase08_api.py`, `tests/test_phase08_openapi.py`, `tests/test_phase08_errors.py`, `tests/test_phase08_security.py` | PASS |
| Stream live events | `tests/test_phase09_websocket.py`, `tests/test_phase13_live_monitor.py`, `tests/test_phase13_timeline.py` | PASS |

## Verification run

```console
uv run pytest -q
```

Result: `496 passed, 17 skipped`. The skips are opt-in browser/interop scenarios; the
scheduled implementation-facing interop run was executed separately:

```console
LUMORA_INTEROP=1 uv run pytest -m interop tests/interop -q -ra
```

Result: `14 passed, 0 failed` against DCMTK, dcm4che, and Orthanc. Evidence is retained in
`docs/planning/phase-20-interop-results.md`.

## Scope interpretation

The matrix validates the engineering platform capabilities named by the PRD. It does not
convert Lumora Probe into a PACS, RIS, EMR, diagnostic workstation, or clinical archive.
Known protocol/security/deployment limitations are recorded in
`docs/guides/known-limitations.md` and are not hidden by this acceptance matrix.
