# ADR-0037: Release-Closure Performance Gates

- **Status:** Accepted
- **Date:** 2026-08-01
- **Deciders:** Lumora Probe maintainers

## Context

ADR-0030 ratifies capture volume and rolling-retention limits. Release closure also needs structural
storage gates and reproducible timing evidence for pagination, rebuild, and ring expiry without
turning a generic hosted runner into a universal performance promise.

## Decision

Structural gates run on every PR. Reference timing is release evidence only and must identify host,
filesystem, Python/SQLite versions, warm-up, at least five samples, median/p95 method, and noise
policy. Reference identity for the first closure run is the macOS developer host's local SSD on
CPython 3.13 with the release commit recorded; hosted-runner results remain informational.

| Workload | Blocking structural gate | Reference target |
|---|---|---|
| Collection pages at 10,000 captures / 100,000 instances / 500,000 events | SQL count plus bounded page query; page-owned children only; no filesystem stats/opens | p95 <= 250 ms |
| Sort/filter pages | SQL filtering/sorting, deterministic unique tie-breaker, no full materialization | p95 <= 500 ms |
| Full rebuild | One final study/series projection rebuild; no ready state before completion | <= 60 s |
| N versus 2N rebuild | One projection rebuild; statement/byte growth is non-quadratic | 2N median <= 3x N |
| Ring steady state | Eviction writes bounded by segment size; no retained-set rewrite | amplification <= 4x accepted bytes after warm-up |

Timing misses require profiling before caches or alternate authoritative stores. Structural gates do
not claim a timing pass. ADR-0030 remains the hard volume/retention decision.
