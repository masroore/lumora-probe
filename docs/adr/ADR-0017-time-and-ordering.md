# ADR-0017: Three Time Concepts; Sequence Is the Only Ordering Authority

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

`06` §6 gives one time field, `occurred_at`, as an ISO-8601 UTC string. `06` §9 then
says consumers "SHALL rely on `occurred_at`, `correlation_id`, `aggregate_id` instead of
arrival order."

That instruction cannot be safely followed, because wall-clock time is not monotonic.
NTP slews and steps during long captures, a suspended laptop resumes with a jump, and on
a busy host two events land in the same microsecond. The consequences are all on primary
paths:

- Sorting the timeline by `occurred_at` can invert causal order — `DatasetParsed` before
  `CStoreReceived`. The screen the product exists for silently lies.
- Receive and decode durations (`02` §13 displays both) can come out **negative** across
  an NTP step.
- Replay timing reconstructed from wall deltas replays the NTP correction as a pause.

## Decision

Three concepts, each with exactly one job:

- **`occurred_at`** — wall clock, UTC. Display and cross-capture correlation only. Never
  ordering, never arithmetic.
- **`monotonic_ns`** — capture-relative, from `time.monotonic_ns()`. All durations and
  all inter-event gaps.
- **`sequence`** — a per-capture, gap-free integer assigned by ADR-0002's loop-owned
  sequencer at publish. The sole authority for order.

The manifest records one wall+monotonic anchor pair at capture start, so wall time is
reconstructible from monotonic.

This is what makes `06` §9's guarantee deliverable rather than aspirational: ordering
within an aggregate and within a capture session becomes a property of an integer
assigned at one point — exactly what ADR-0002's single-owner bus bought.

**A gap-free sequence makes event loss provable.** If `events.jsonl` jumps 4102 → 4104,
an event was lost, and any consumer can detect it without trusting our logs. That closes
the loop on ADR-0002's drop policy: `EventsDropped` becomes auditable against the
artifact instead of asserted, and `11` §11's integrity verification gains a second cheap
check alongside object digests.

**Clock anomalies become findings, not corrupt data.** When wall delta and monotonic
delta diverge beyond a threshold, a `ClockAnomalyDetected` warning event records both.
That covers NTP steps and suspension — worth noting that `time.monotonic()` excludes
suspended time on macOS but not Linux, so the two platforms disagree about a sleeping
machine, and this event is how that surfaces rather than silently skewing a capture.
`01` §6 applied to our own instrumentation.

## Alternatives Considered

- **`occurred_at` only.** `06` read literally; unsafe for the reasons above.
- **Hybrid logical clocks.** Correct for a distributed system, which this is not. When
  remote collectors arrive (ADR-0007), each gets its own sequence space keyed by
  collector ID and we continue to make no cross-collector total-order claim — consistent
  with `06` §9's "global ordering is NOT guaranteed".

## References

`01` §6 · `02` §13 · `06` §6, §9 · `11` §11 · ADR-0002 · ADR-0007
