# ADR-0012: Module-First Package Structure With CI-Enforced Boundaries

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

Two incompatible primary axes, both called binding. `03` §4 defines four layers —
Presentation, Application, Domain, Infrastructure — with hard rules. `05` defines 16
modules, forbids depending on another module's internals (§21), and calls module
boundaries "architectural contracts" (§24).

Layer-first smears Capture Engine across four packages, so nothing structurally
represents the contract `05` declares. Module-first demotes `03`'s layers to a
per-module convention.

A second problem: `05`'s 16 modules are not the same kind of thing. Association
Manager, Capture Engine, Replay Engine, Storage and Plugin Host are bounded contexts
with lifecycles. Dashboard, Event Timeline and Metadata Inspector are **views over data
other modules own** — no state, no domain. Making all 16 into packages produces empty
shells that make coupling look fine because nothing lives in them.

## Decision

**Module-first, layers inside each slice.**

```
lumora/
  core/       # bus, config, ids, clock, errors, storage primitives
  shared/     # DICOM value objects, event envelope + payload registry
  associations/  captures/  replay/  studies/
  analysis/      reports/   plugins/  settings/
  web/        # HTMX templates, view composition, UI socket adapter
```

Each slice contains its own `domain.py`, `service.py`, `repository.py`, `api.py` and a
public `contracts.py`. Dashboard, Live Monitor, Event Timeline, Metadata Inspector and
Viewer are presentation in `web/` over existing slices — no fake packages. Storage
splits: primitives in `core/`, per-slice repositories in their slices. `captures/`
includes the ring buffer; `studies/` covers Patient/Study/Series/Instance and metadata.

**Boundaries are machine-enforced, not documented.** `import-linter` (dev-only, so
`04` §14 is not strained) with explicit contracts:

- `core` imports nothing from slices; `shared` imports only `core`.
- Slices may import `core`, `shared`, and other slices' `contracts.py` **only**.
- `web` imports slices; no slice imports `web`.
- Nothing imports plugin internals.
- No `domain.py` may import FastAPI, SQLAlchemy or Jinja.

`13` §15 already requires static analysis as a quality gate, so this rides an existing
hook. Without it, `05` §24's "architectural contracts" are a comment.

The last contract is how `03` §4's layering is preserved — as a lint rule rather than a
directory shape, which is the part that actually holds.

## Alternatives Considered

- **Layer-first.** Rejected: `05` §21's dependency rule becomes unstateable, since
  every module's code sits in the same four packages and no import graph can express
  "Capture must not reach into Replay's internals".
- **Both axes (modules inside layers).** Rejected: four times the directories for no
  additional enforcement.

## Consequences

- Cross-slice reads go through the bus or a contract-typed service call, **never** a
  repository. Two slices sharing a SQLite file is fine; sharing a repository object is
  how `05` §22's ownership quietly dissolves.
- The per-slice public surface is the same one plugins see (ADR-0006, ADR-0021).

## References

`03` §4 · `04` §14 · `05` §21, §22, §24 · `13` §15
