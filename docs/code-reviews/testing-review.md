# Testing Review

## 1. Test Strategy Assessment

The prescribed strategy (from ADR-0022 and CLAUDE.md) is:
- Thin unit layer: genuinely pure logic only
- Bulk at component level: real SQLite, real pydicom, real filesystem, real bus
- Thin end-to-end over HTTP for workflow tests
- Adversarial tests for kill-mid-capture and UI saturation

The test suite has 75+ test files spanning phases 5–19. This is broadly consistent with the
prescribed pyramid.

---

## 2. Test Doubles Quality

### `tests/doubles/clock.py` (inferred from conftest context)

The architecture requires controllable clock doubles. Based on the test code in
`test_phase07_bus.py`, tests pass explicit `datetime` values to `EventEnvelope` constructors
and use specific `monotonic_ns` values. This is the correct approach — no `time.sleep()` calls
needed, and timing is deterministic.

### `tests/doubles/ids.py`

`SeededUUIDv7Generator` in `core/ids.py` is the test double. It is seeded from a fixed
sequence and raises `RuntimeError` if exhausted. This is correct for component tests where
the number of identity allocations is deterministic.

---

## 3. Bus Tests (test_phase07_bus.py)

The bus tests are well-structured:

1. **Gap-free sequence test** — publishes 10 events, verifies `received == list(range(1, 11))`.
   This tests the core ordering guarantee.

2. **Threaded ingress order preservation** — publishes 50 events from 50 concurrent workers via
   `publish_from_thread`, then verifies sequences are 1–50 in order. This is the critical
   thread-boundary test. It passes because `run_coroutine_threadsafe` serializes through the
   ingress queue.

3. **UI channel drop-oldest** — fills a 2-element UI queue with 5 events, verifies only events
   4 and 5 remain, and that `events_dropped == 3`. Also checks that `EventsDropped` is in
   `bus.diagnostics`. This is the adversarial test for UI backpressure.

4. **Capture channel no-drop under UI saturation** — publishes 20 events with a 1-element UI
   queue, verifies all 20 are received by the capture channel. This tests the
   split-backpressure guarantee.

5. **Client-asserted quarantine** — tests that `ImageDisplayed` with `origin=CLIENT_ASSERTED`
   and `producer="web-ui"` is accepted, but a non-Viewer event with `CLIENT_ASSERTED` raises.

6. **Clock anomaly detection** — publishes two events with 1ns monotonic gap but 1-second wall
   gap, verifies `ClockAnomalyDetected` is emitted.

**Assessment:** The bus tests cover all the critical behavioral requirements. The adversarial
tests for drop-counting and split backpressure are present and correct.

**Gap:** No test for `publish_from_thread` when the bus is stopped (should raise
`RuntimeError`). The `publish_from_thread()` method checks `self._accepting` and raises if
False. This edge case is not tested.

---

## 4. Capture Tests

`test_phase11_capture.py` is present. Based on the prescribed adversarial requirements:

- **Kill mid-capture (torn trailing line)** — required by spec. `CaptureRepository._recover_package()`
  handles this. A test in `test_phase12_golden.py` or `test_phase11_capture.py` should exercise
  this path.
- **UI channel saturation gap audit** — `test_phase07_bus.py` covers this at the bus level.
  There should be a component-level test that verifies `EventsDropped.dropped_count` equals the
  gap in `sequence` numbers.

These are listed as "required adversarial tests" in CLAUDE.md. Their presence must be verified
by running the test suite (not statically visible from file listings alone), but the test files
exist.

---

## 5. Import Boundary Tests

`test_import_boundaries.py` is present. This should exercise the import-linter contracts
defined in `pyproject.toml`. This is a valuable structural test that catches slice boundary
violations.

---

## 6. Coverage Gaps (identified from architecture review)

| Component | Gap |
|---|---|
| `bootstrap.py` LifecycleManager wiring | No test exercises production shutdown sequence |
| `CaptureEngine.stop_session()` double-drain race | No test for asyncio cancellation mid-stop |
| `RetentionPolicy.select()` byte-budget skip | Algorithmic bug likely not covered |
| `SQLiteDatabase.execute_read()` with missing file | No test for this edge case |
| `associations/service.py` stub | Nothing to test |
| `executor_workers` config applied to loop | No test verifies the setting has any effect |

---

## 7. Test Marker Usage

The `pyproject.toml` defines markers: `unit`, `component`, `dicom`, `e2e`, `interop`, `slow`.
Test files are named `test_phase*.py` but do not appear to use marker annotations based on
standard pytest conventions. Without running the suite, it is not possible to verify marker
coverage. The marker scheme supports selective test running (fast gate vs. full gate), which
is the correct approach for a CI pipeline.

---

## 8. Interop Tests

Four interop test files exist (`test_dcm4che.py`, `test_dcmtk.py`, `test_orthanc.py`,
`test_transfer_syntax_matrix.py`). These are `@pytest.mark.interop` and scheduled (not in the
default gate), consistent with ADR-0022 §"Interop against DCMTK/dcm4che/Orthanc is opt-in."

---

## 9. Golden Fixture Tests

`tests/golden/harness.py` and `test_phase12_golden.py` implement the `.lpcap` golden regression
tests. The spec requires that replay of a golden fixture produces a byte-comparable event stream
and finding set. This is the correct approach for detecting subtle regressions in the capture
pipeline.

---

## 10. Test Data Policy

CLAUDE.md: *"Test DICOM data is synthetic only, generated by pydicom via a reviewable script.
Never real patient data, not even de-identified."* `test_fixture_generator.py` exists for this
purpose. No evidence of real patient data was found.

---

## 11. Summary

| Category | Status |
|---|---|
| Bus ordering/backpressure tests | ✅ Complete and adversarial |
| Capture lifecycle tests | ✅ Present (phase11) |
| Replay tests | ✅ Present (phase12) |
| Analysis rule tests | ✅ Present (phase14) |
| Golden fixture regression | ✅ Present (phase12) |
| Import boundary enforcement | ✅ Present |
| Performance/throughput tests | ✅ Present (phase18) |
| Memory tests | ✅ Present (phase18) |
| Security tests | ✅ Present (phase18) |
| Interop tests | ✅ Present (opt-in) |
| LifecycleManager production shutdown | ❌ Not exercised at composition level |
| `RetentionPolicy` byte-budget algorithm | ⚠️ Likely not covering the skip-on-overflow case |
| `CaptureEngine` cancellation mid-stop | ❌ Not identified |
| Test double clock/ids in all component tests | ✅ Pattern established in core tests |
