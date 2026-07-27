# ADR-0014: Two Tiers — Domain Events on the Bus, Protocol Trace Beside It

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

ADR-0005 committed to recording PDU-level structure and described it as "cheap, small".
That was wrong, and this record corrects it.

Default max PDU length is 16 KB, so a 512 KB CT instance is ~32 P-DATA-TF PDUs and a
500-instance study is ~16,000. The "Large Enhanced MR datasets" named in `01` §3 run to
thousands of instances, so hundreds of thousands of PDUs. At a full canonical envelope
per PDU (~350–500 bytes of JSON, where the envelope dwarfs the payload) that is tens to
hundreds of MB of `events.jsonl` for one study, it would consume ADR-0008's 2 GB ring
buffer in minutes of real traffic, and every one of those would pass through ADR-0002's
loop-owned sequencer on the path that must stay responsive for WebSocket fan-out.

`06` §3 says "every meaningful state transition emits an event". A PDU arriving is not a
state transition of an aggregate — it is telemetry about one.

## Decision

**Domain events** go on the bus with the full envelope, versioned, in the catalog,
visible to UI and plugins: roughly 6–10 per instance (`CStoreReceived`,
`DatasetParsed`, `ImageDecoded`, `InstancePersisted`, …).

**Protocol trace records** never touch the bus. PDU-level rows are written directly to
a separate compact append-only stream in the capture (`pdus.jsonl`, minimal fields, no
envelope), keyed to association and message so Transfer Analysis and the timeline can
pull them on demand.

**Summaries are the default view.** Every DIMSE domain event payload carries derived
fields — PDU count, bytes, first/last timestamp, max inter-PDU gap — so throughput,
stalls and fragmentation are answerable from events alone. The trace exists for
drill-down.

This keeps the bus at ~5,000 events for a 500-instance study, keeps `events.jsonl`
greppable by a human (ADR-0004's rationale), spends the ring buffer's budget on objects
rather than PDU envelopes, and still gives Transfer Analysis the resolution to be honest
about ADR-0003's per-leg timing.

**ADR-0005's `fidelity` field now names streams:** `events` → `protocol` (adds
`pdus.jsonl`) → `wire` (adds raw bytes). The manifest lists which are present; replay
refuses modes whose stream is absent.

**`02` §20's four outputs are rejected as written.** It lists stdout, `app.log`,
`events.jsonl` and SQLite, and `05` §14 has Logging consume every event — writing every
domain event four times on the hot path is the easiest way to make this tool slower than
the traffic it observes. Instead: `events.jsonl` is the sole durable event record;
SQLite holds the rolling index window (ADR-0004); `app.log` carries **operational**
logging about the application, not a mirror of domain events; stdout is the
human-readable view of `app.log`. structlog remains the logging layer with correlation
IDs shared with events per `14` §8, so the streams cross-reference rather than
duplicate.

**Metrics are derived from the event stream**, not separately instrumented — one
counting path, so `14` §6's metrics cannot disagree with `14` §4's events. In-process
registry exposed on the API and dashboard; Prometheus exposition can arrive later as a
plugin rather than a core dependency, since no metrics library is in `04`.

## Consequences

- Domain event volume per instance is bounded, so "the bus stalled" becomes a testable
  regression (`13` §12) rather than a vague worry.

## References

`01` §3 · `02` §20 · `05` §14 · `06` §3 · `13` §12 · `14` §4, §6, §8 · ADR-0002 ·
ADR-0005 · ADR-0008
