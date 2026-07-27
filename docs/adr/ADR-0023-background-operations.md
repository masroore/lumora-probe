# ADR-0023: In-Memory Jobs With Durable Audit; Never Auto-Resumed

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

`17` §14 lists Background Job Architecture as an expected ADR topic. `08` §12 requires
long-running operations to return immediately, provide operation identifiers and expose
progress endpoints. `03` §11 names capture import, replay, report generation and metadata
indexing as async. `04` §13 excludes Celery, RabbitMQ, Kafka and Redis, and ADR-0007 gave
us one process — so this is asyncio tasks plus an executor. The only open question is what
survives a restart.

The operations: protocol replay (ADR-0005), report generation, ring-buffer promotion
(ADR-0008), folder import (ADR-0013), index rebuild (ADR-0004), `.lpcap` pack/unpack.

## Decision

**In-memory execution, durable audit, never resumed.** Every operation gets a UUIDv7 ID
and a persisted record — type, parameters, start, end, outcome, progress checkpoints — but
execution state lives only in memory. At startup, anything still marked `running` is
transitioned to `Interrupted` with the reason recorded. Nothing auto-continues.

**A durable resumable job table is actively unsafe for the job that matters most.** A
protocol replay writes real C-STOREs into a real PACS. Auto-resuming a half-finished
900-instance replay after a crash duplicates an unknown number of objects, because we
cannot know which in-flight sends the peer committed. Every guardrail in ADR-0005 —
dry-run default, target allowlist, audit log — would be defeated by a resume nobody
initiated. Resumption is worthless for the rest anyway: reports are cheap to redo, index
rebuild is idempotent by construction, and import and promotion should restart clean
rather than resume into a half-sealed manifest.

**Progress rides the bus.** Jobs publish progress as domain events; the UI receives them
through ADR-0019's coalescing governor with no new mechanism, and
`/api/v1/operations/{id}` reads the same registry. `08` §12 satisfied without a second
transport.

**The application database splits in two, physically.** ADR-0004 and ADR-0011 made the DB
a rebuildable index; ADR-0020 already had to route runtime settings around that rule, and
job history is the second thing that is not re-derivable.

- `index.db` — study/series/instance projections, capture index, rolling event window.
  Droppable and rebuildable at any time.
- `app.db` — job history, audit log, bookmarks. Authoritative, and the only file needing
  backup.

That makes "blow away the index" a documented recovery step rather than a data-loss event,
and gives `11` §11's backup guidance a precise target.

**Cancellation is cooperative and must report where it stopped.** Cancelling a replay
mid-flight leaves partial objects in the target, so the record states how many instances
were sent and confirmed. A job reporting only `cancelled` is the silent failure `03` §12
prohibits, in the place it costs most.

**Concurrency is bounded per job type, and replay is exclusive** — one protocol replay at
a time, refused with a structured error rather than queued, since concurrent replays into
one target interleave associations and make both results uninterpretable. Reports and
imports run with a small worker limit against ADR-0002's executor.

No new dependencies, keeping `04` §13 intact.

## References

`03` §11, §12 · `04` §13 · `08` §12 · `11` §11 · `17` §14 · ADR-0002 · ADR-0004 ·
ADR-0005 · ADR-0011 · ADR-0019 · ADR-0020
