# ADR-0002: Loop-Owned Event Bus With a Single Thread Boundary

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

The approved stack is split down the middle. FastAPI, Uvicorn and WebSockets are
async by nature. pynetdicom is thread-per-association (handlers such as
`EVT_C_STORE` run on the association's own thread), while pydicom parsing, pixel
decode, SQLAlchemy Core + SQLite and DuckDB are all blocking. The event bus — "the
heart of Lumora Probe" (`03` §5) — sits between the two.

`06` §15 says the bus "SHALL dispatch synchronously or asynchronously". That
constrains dispatch modes, not ownership. The threading model is unspecified.

## Problem Statement

Who owns the bus? The answer determines repository signatures, background service
shape, capture durability, WebSocket fan-out and every test fixture. Deciding late
means rewriting most of the implementation phases.

## Decision

The **asyncio event loop owns the bus** and is the sole authority for event ordering.

- pynetdicom threads publish through a thread-safe ingress
  (`loop.call_soon_threadsafe` onto a bounded queue). This is the only thread
  boundary in the system.
- Blocking work — dataset parse, pixel decode, SQLite writes, report generation —
  runs in explicit executors, never on the loop.
- Repository interfaces are `async def`.
- The bus accepts async subscribers (awaited) and sync subscribers (called inline,
  contractually non-blocking), satisfying `06` §15.

**Backpressure is split by purpose.** `06` §10 requires durable capture persistence
while `09` §12 asks for event-dropping policies; those are contradictory with one
queue. The capture/persistence path never drops. UI and WebSocket channels use
bounded queues with drop-oldest plus an `EventsDropped` counter surfaced in the UI —
silent dropping would violate `03` §12.

**Subscriber time budget.** Each subscriber has a per-event budget; breaching it
raises a warning event. Anything genuinely slow runs in an executor or a background
service, not on the bus.

## Alternatives Considered

- **Sync-first core, async only at the API edge.** Rejected: makes the WebSocket
  path — highest fan-out, lowest latency requirement — the awkward one, and fights
  FastAPI's grain permanently.
- **Dual-mode bus with no privileged owner.** Rejected: two execution contexts with
  no owner has no single answer to "what order did these arrive in", which is the
  question the product exists to answer.

## Consequences

- `06` §9's ordering guarantee becomes a property of one sequencer rather than a
  locking argument (see ADR-0017).
- A stalled loop is a capture-integrity risk, hence the time budget above.
- The DICOM edge needs a Phase 11 spike to confirm pynetdicom threading empirically;
  the boundary exists under any plausible model, so the core decision does not wait.

## Risks

- A misbehaving sync subscriber blocks everything. Mitigated by budget, warning
  events, and executor offload for known-slow work.

## References

`03` §5, §11, §12 · `04` §4–6 · `06` §9, §10, §15 · `09` §12
