# ADR-0007: Single Process With a Transport-Abstracted Bus Ingress

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

`04` §13 excludes Redis, RabbitMQ, Kafka and Celery. With no broker and no ORM,
cross-process eventing means inventing IPC the baseline never sanctioned, against
`04` §2's minimal operational complexity and the Charter's local-first principle.

But `03` §16 requires accommodating distributed collectors and remote agents "without
fundamental redesign", and `05` treats the DICOM-facing modules and the REST API as
separately owned.

## Decision

**One process now, with the bus ingress defined as a transport-abstracted boundary.**

Local publishers (SCP threads, background services) and a future remote collector
enter through the same ingress contract. The remote case becomes an authenticated
HTTP/WS publisher endpoint added later — not a bus redesign. ADR-0002 already
requires a thread→loop ingress, so defining it as an interface rather than a concrete
call is nearly free.

**One `Service` protocol** — start / stop / health — over heterogeneous components:
loop tasks, the thread-based SCP, executors, background workers. The lifecycle manager
owns ordered startup and reverse-ordered shutdown and reports per-service health to
`14` §9's endpoints.

**Shutdown must drain.** `06` §10 promises durable capture persistence; a process that
drops its last events on SIGTERM breaks that quietly. Sequence: stop accepting new
associations → drain the ingress queue → flush and fsync the capture writer → close.
Bounded grace period; if the deadline is hit, the manifest records
`CaptureInterrupted` rather than leaving a silently truncated capture.

**Crash recovery is a built path, not a hope.** One process means one crash takes the
live capture. Because `events.jsonl` is append-only and the index is rebuildable
(ADR-0004), restart recovery is: scan the capture directory, discard a torn trailing
line, mark the capture `Interrupted`, re-derive the index. Built and tested in Phase
12 (ADR-0022).

**The CLI is a client, not a second runtime.** `03` §7 makes everything available
headless and `03` §10 makes the REST API canonical, so `lumora` talks to a running
server over `/api/v1`. One-shot embedded execution is allowed for offline work such as
`lumora capture inspect <file>`; anything touching live state goes through the API.
Otherwise there are two lifecycle managers, two bus instances and two SQLite writers
contending on one file.

**The DICOM listener binds 11112**, not 104: port 104 requires root or `CAP_NET_RAW`,
and running the platform as root is unacceptable under `12` §3.

## Alternatives Considered

- **Split collector and API processes now.** Rejected: a bespoke broker in Phase 05
  for a requirement with no user story, and ADR-0002's ordering sequencer would become
  a distributed ordering problem.
- **Single process with no ingress abstraction.** Fine today, expensive exactly once —
  the moment a remote agent is asked for.

## References

`03` §7, §10, §16 · `04` §2, §13 · `05` · `06` §10 · `12` §3 · `14` §9
