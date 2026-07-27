# ADR-0004: Captures Are Self-Contained Directories; `.lpcap` Is the Interchange Form

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

`03` §9 requires captured evidence to remain portable. `11` §3 requires immutable
evidence. `06` §16 requires captured events persisted "exactly as published". `05` §7
requires the Capture Engine to *package* captures. `11` §6 leaves the physical schema
unspecified, and `11` §5 lists a capture repository and an event store as separate
components without relating them.

## Problem Statement

SQLite is the operational database and a single `.db` file is already portable. So is
a capture just rows in the application database, or a separate artifact?

## Decision

A capture is a **self-contained directory**; the application database holds only a
derived index.

```
captures/<uuid7>/
  manifest.json      # identity, provenance, fidelity, digests, clock anchor
  events.jsonl       # canonical envelopes, verbatim, append-only
  pdus.jsonl         # protocol trace (ADR-0014), present at fidelity >= protocol
  objects/<sha256>   # content-addressed received datasets
  logs/
  analysis/          # regenerable findings (ADR-0018)
```

Interchange form is `.lpcap` — the directory zipped with deflate. The directory is
the working form.

**The application database is a rebuildable cache, not a source of truth.** If the
index disagrees with the capture directory, the directory wins and the index is
re-derived. Dropping a `.lpcap` into the captures folder makes it appear.

**Objects are content-addressed** (SHA-256 filenames, digest list in the manifest).
This deduplicates re-sent instances — common in the failure modes being diagnosed —
and delivers `11` §11's integrity verification for free.

## Alternatives Considered

- **Everything in the application database.** Rejected: handing over one capture
  would mean shipping the whole database, including every other site's PHI. That is a
  `12` violation, not an inconvenience.
- **One SQLite file per capture.** Rejected: `06` §16 requires byte-faithful event
  persistence, which append-only JSONL gives directly. JSONL is crash-tolerant (a torn
  trailing line is recoverable; a torn SQLite write during live capture risks the
  file), streams without loading, and is greppable by an engineer with no Lumora
  tooling. DuckDB — already approved — reads JSONL natively, so analytical query power
  is not lost.

## Consequences

- Redaction becomes a defined transform: read capture, write a new capture with a new
  ID, record the source and profile in the manifest (ADR-0026). Immutability and
  provenance both preserved.
- `11` §13's secure deletion is `rm -rf` of one directory, not a hunt through shared
  tables.
- Migrations get cheaper: the operational schema can be recreated rather than
  carefully migrated.
- Two stores must be kept coherent, and JSONL has no referential integrity. Accepted;
  the index being derived is what makes it tolerable.

## Risks

- Directory-level corruption from external tampering. Mitigated by manifest digests
  and the gap-free event sequence (ADR-0017).

## References

`03` §9 · `05` §7 · `06` §16 · `07` §12 · `11` §3, §5, §6, §11, §13 · `12` §9
