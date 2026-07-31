# Phase 18 Performance Report

**Date:** 2026-07-31
**Posture:** Option B (preserve ADR-0030 gates; measure unresolved dimensions)
**Commit:** recorded at completion; see `phase-18-completion-report.md`

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
