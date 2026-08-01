# ADR-0035: Direct sqlite3 for Local Persistence

- **Status:** Accepted
- **Date:** 2026-08-01
- **Deciders:** Lumora Probe maintainers

## Context

The architecture baseline names SQLAlchemy Core as the persistence technology, while the
implemented application uses the Python standard-library `sqlite3` module behind explicit
single-writer and read-only connection seams. The implementation has no ORM and does not need
SQL construction shared across database vendors. Replacing the working storage layer solely to
match the historical baseline would add a runtime dependency and migration risk without a
measured product benefit.

## Decision

Ratify direct `sqlite3` as Lumora Probe's local persistence implementation. `StorageDatabases`
remains the only composition-facing database boundary. New code must use its connection and
transaction APIs, preserve WAL/busy-timeout/local-filesystem policy, and keep explicit row-to-domain
mapping in repositories.

SQLAlchemy is not a runtime dependency. A future migration requires a separate ADR with measured
benefit, compatibility tests, and a rollback plan.

## Consequences

- The baseline's SQLAlchemy wording is historical architecture context, not an installation
  requirement.
- The standard library keeps the distribution smaller and avoids an unused dependency.
- SQL remains hand-written and must remain parameterized; repository tests and import boundaries
  are the correctness gates.
- Database portability beyond SQLite is intentionally not a v1 requirement.
