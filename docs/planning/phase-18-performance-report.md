# Phase 18 Performance Report

**Date:** 2026-07-31
**Posture:** Option B (preserve ADR-0030 gates; measure unresolved dimensions)
**Commit:** `17fa82b` (release-closure evidence tip; Phase 18 historical measurements remain below)

## Environment identity

| Field | Value |
|-------|-------|
| OS | macOS (darwin) — reference developer host |
| CPU / RAM | Host class as available to the test runner |
| Python | 3.13+ (project requires 3.13+) |
| Workload seeds | Deterministic synthetic UIDs under `1.2.826.0.1.3680043.10.543.18.*` |
| Method | Component tests in `tests/test_phase18_*.py`; monotonic timers; no fixed sleeps for readiness |

Unratified dimensions are labeled **measured**, **limited**, or **not verified**. They are not
pass/fail against invented thresholds.

## Results

| Dimension | Workload | Interpretation | Status |
|-----------|----------|----------------|--------|
| Startup | Five isolated `lumora serve` starts; poll `GET /api/v1/health/ready`; separate `build_production_app()` timing | Evidence only | measured (`test_phase18_startup.py`) |
| Large study | 2,000 synthetic instance projections; browser + paginated API; no pixel decode | Correctness hard; latency evidence | measured (`test_phase18_large_study.py`) |
| Event throughput | 5,000 domain events through bus + capture subscriber + governor flush | Durable path not dropped; Phase 09 <100 ms governor gate retained separately | measured (`test_phase18_throughput.py`) |
| Memory | Three ring fill/eviction cycles at 64 KiB cap; RSS when available | ADR-0030 byte cap hard; RSS trend evidence | measured (`test_phase18_memory.py`) |
| Replay | 500 `ProtocolReplayDataset` records with injected sleeper | Ordering/timing reconstruction hard; elapsed evidence | measured (`test_phase18_replay_performance.py`) |
| Concurrent clients | 1 / 4 / 8 `/ws/ui` + 1 `/api/v1/events/stream` | Drop/error accounting hard; counts are workload identity | measured (`test_phase18_concurrent_clients.py`) |
| UI interaction | Existing 5,000-event/<100 ms server flush; ADR-0031 no-round-trip smoke | Scoped gates retained; not an end-to-end browser latency ADR | limited (existing Phase 09/13 coverage) |

## ADR-0030

Existing `tests/test_phase11_budgets.py` remains the hard capture volume/retention gate. No
ADR-0030 miss was observed during Phase 18.

## F-06

F-06 remains **OPEN**. This report is linked from
`docs/planning/00-architecture-review-findings.md`. Unratified dimensions: startup, large-study
latency, process memory trend, replay elapsed, concurrent-client capacity, end-to-end browser
latency.

## Release-closure measurements (2026-08-01)

**Commit under evaluation:** `17fa82b` (release-closure evidence tip). **Reference host:**
macOS local SSD, CPython 3.13,
SQLite WAL. **Method:** one warm-up plus five samples for timing runs; median and p95 are reported
when a workload is run. No result below is generalized to network filesystems.

| Gate | Structural evidence | Timing evidence | Status |
|---|---|---|---|
| Bounded pagination | `CaptureRepository.list_captures_page()` performs count + page + page-owned object query; projection store uses parameterized SQL `LIMIT/OFFSET`; direct lookup uses `WHERE` | `tests/performance/test_release_closure.py` and Phase 18 workloads | measured / structurally implemented |
| Projection rebuild | `CaptureRepository.rebuild()` indexes valid packages with projection disabled and invokes one final projection rebuild | Existing Phase 18 startup/large-study measurements | measured / structurally implemented |
| Ring expiry | Persisted append-only `segments/` metadata; eviction deletes or compacts only affected segments; oversized records remain as a single retained segment; legacy `records.jsonl` migrates after durable segment metadata | `RingBufferService.persistence_stats`; structural turnover, torn-tail, migration, oversized-record, and metadata-publication tests | measured / structurally implemented |
| Installed artifacts | Wheel smoke driver verifies site-packages imports, static assets, HTTP readiness, DICOM C-ECHO/C-STORE, promotion, and shutdown | Local wheel and sdist smoke passed; hosted six-job matrix passed in CI run `30714291883` | pass locally and hosted |
| Warning cleanliness | Pytest defaults to `error`; direct SQLite fixtures and locked pynetdicom transport teardown are closed explicitly | `uv run pytest -q -W error`: 553 passed, 17 skipped | pass locally |

The current structural release-closure suite also covers deterministic unique pagination ties,
direct projection point lookups, SQL query-plan presence for the indexed instance sort, and a
real child-process forced-deadline capture recovery. It does **not** constitute a reference timing
run for the 10,000-capture / 100,000-instance / 500,000-event workload, N-versus-2N rebuild
scaling, or the five-sample p95 budgets in ADR-0037; those remain explicitly unverified rather
than being inferred from small structural fixtures.

Hosted matrix evidence is now recorded in CI run `30714291883`; reference timing remains open.
The run’s scheduled external interoperability job was skipped, so no final-SHA interop claim is made.
This report does not convert local structural evidence into a universal latency claim.
