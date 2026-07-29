# ADR-0030: Ratified Capture Volume and Retention Budgets

- **Status:** Accepted
- **Date:** 2026-07-29

## Context

`docs/planning/provisional-non-functional-budgets.md` recorded capacity thresholds for
Phase 11, but they were not release commitments. The capture engine now has bounded event,
protocol, and rolling-buffer paths that can be measured with representative synthetic study
traffic.

## Decision

Promote the following thresholds to release gates:

| Area | Ratified gate | Measurement |
| --- | --- | --- |
| Domain events | At most 10 events per instance on average; at most 5,000 for a 500-instance study | Count canonical event records in the capture package |
| Protocol trace | Plan for at most 32 compact PDU records per 512 KiB instance; at most 16,000 for a 500-instance study | Count `pdus.jsonl` records and compare with instance byte totals |
| Always-on ring buffer | 30 minutes retention and a hard 2 GiB byte cap | Assert oldest retained age and `bytes_used` under sustained traffic |
| Capture persistence | Capture and ring writers must not exceed configured byte limits or silently drop durable session events | Component tests with real filesystem and injected clock |

The ring buffer is allowed to evict only records outside the configured retention window or
when the configured byte cap requires eviction. Explicit capture sessions remain unbounded
until sealed or interrupted.

Raw wire capture is not included in these gates. The current implementation must refuse a
request for `wire` fidelity rather than claim a stream it cannot produce.

## Evidence

The Phase 11 representative synthetic workload writes 5,000 domain-event records and
16,000 protocol records for 500 instances. The local component measurement on July 29,
2026 retained 21,000 records using 520,380 bytes. The budget test is deterministic and
asserts the volume and retention gates; hardware-specific latency is not claimed as a
release guarantee.

## Consequences

- Performance tests use the ratified thresholds, not provisional labels.
- Any future change that increases event or PDU cardinality must update this ADR or add an
  explicitly versioned exception.
- Deployment sizing may use measured traffic and the 30-minute/2-GiB ring cap independently
  of the operational SQLite index.

## References

ADR-0004 · ADR-0008 · ADR-0014 · ADR-0017 · ADR-0022 · `provisional-non-functional-budgets.md`
