# Phase 05 Completion Report — Domain Model

**Date:** 2026-07-29  
**Status:** Complete

## Completed work

- Added plain-Python immutable DICOM value objects using frozen, slotted dataclasses:
  - AE titles
  - DICOM UIDs and transfer syntaxes
  - Network endpoints
  - Presentation contexts
  - Timestamps and durations
  - File paths
  - DICOM tags
  - Pixel dimensions
  - Window level and width
- Added domain error taxonomy with stable remediation-bearing errors, separate from
  Pydantic boundary errors.
- Added Association aggregate with DICOM lifecycle transitions.
- Added AssociationPair aggregate with independently represented downstream, Probe-hop,
  and upstream legs.
- Added Capture aggregate with:
  - `Created → Running → Stopping → Completed → Archived`
  - `Interrupted`
  - promoted ring-buffer metadata
  - partial capture metadata
- Added Replay aggregate with event/protocol modes, fidelity requirements, explicit target
  enforcement, dry-run default, and lifecycle transitions.
- Added Report aggregate recording capture identity and rule-set version.
- Added injected `Clock` protocol and production `SystemClock`.
- Added injected `IdGenerator` protocol and UUIDv7 generator.
- Added deterministic test doubles:
  - independently controllable wall clock
  - independently advanced monotonic counter
  - seeded UUIDv7 sequence
- Added import-linter enforcement preventing non-core `lumora_probe` modules from importing
  `time` or `uuid` directly.

## Design decisions

- Domain modules remain framework-independent. They do not import Pydantic, FastAPI,
  SQLAlchemy, or Jinja2.
- Domain invariant and lifecycle failures use the structured core error model rather than
  leaking `ValidationError`.
- `PresentationContext` normalizes accepted UID/string/transfer-syntax inputs into domain
  value objects and rejects duplicate context IDs at the association boundary.
- Association-pair transitions validate every leg before mutating any leg, preventing
  partially transitioned proxy observations.
- Protocol replay requires an explicit target and protocol-or-wire fidelity. Targets are
  never inherited from a capture.
- UUIDv7 generation remains isolated inside `core/`; domain and application slices receive
  IDs through the protocol boundary.

## Files added

- `src/lumora_probe/shared/value_objects.py`
- `src/lumora_probe/shared/errors.py`
- `src/lumora_probe/core/clock.py`
- `src/lumora_probe/core/ids.py`
- `src/lumora_probe/reports/domain.py`
- `tests/doubles/__init__.py`
- `tests/doubles/clock.py`
- `tests/doubles/ids.py`
- `tests/test_phase05_domain.py`
- `tests/test_phase05_primitives.py`

## Files modified

- `src/lumora_probe/associations/domain.py`
- `src/lumora_probe/captures/domain.py`
- `src/lumora_probe/replay/domain.py`
- `.importlinter`
- `tests/test_import_boundaries.py`

## Tests and verification

- Full pytest suite: **211 passed, 1 skipped**.
- Ruff lint: passed.
- Ruff format: passed.
- BasedPyright strict checks for `core` and `shared`: 0 errors, warnings, or notes.
- Import-linter: 7 contracts kept, 0 broken.
- Package build: passed.
- Domain tests cover value-object invariants, lifecycle transitions, pair-leg preservation,
  replay guardrails, report rule-set provenance, clock independence, and deterministic IDs.

## Known limitations

- Aggregate constructors currently accept caller-supplied IDs; application services will use
  the injected `IdGenerator` when those workflows are implemented.
- Timestamp and monotonic samples are not yet attached to aggregate events; event envelopes
  are Phase 07 work.
- Persistence mapping and schema representation are intentionally deferred to Phase 06.
- Association-pair timing attribution fields are represented by separate legs; measurement
  samples and timing calculations are deferred to the networking and event phases.

## Follow-up

Proceed to Phase 06 only after this report is reviewed. Phase 06 must implement the physically
separate `index.db`/`app.db` storage model, capture package format, repositories, and rebuild
semantics without moving persistence concerns into these domain classes.
