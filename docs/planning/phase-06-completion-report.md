# Phase 06 Completion Report — Storage

**Date:** 2026-07-29
**Status:** Complete

## Completed work

- Added physically separate SQLite stores:
  - `index.db` for rebuildable capture, Study/Series/Instance, and event-window projections.
  - `app.db` for authoritative jobs, audit history, and bookmarks.
- Added SQLite connection policy:
  - WAL mode.
  - `busy_timeout`.
  - foreign keys.
  - serialized writes with concurrent-reader support.
  - network-filesystem refusal for SQLite paths.
- Added idempotent `app.db` migration and destructive/rebuildable `index.db` initialization.
- Added explicit row↔projection mapping without an ORM.
- Implemented capture working directories with:
  - versioned `manifest.json`.
  - append-only `events.jsonl` and `pdus.jsonl`.
  - verbatim raw JSONL append support.
  - explicit flush/fsync durability policy.
  - SHA-256 content-addressed objects and atomic writes.
  - object integrity verification.
- Implemented `.lpcap` deflate pack/unpack with zip-slip and symlink rejection.
- Implemented capture discovery for working directories, primary-root `.lpcap` drops, and
  additional read-only capture roots.
- Implemented deterministic index rebuild and canonical projection snapshots for byte
  comparison.
- Implemented retention selection by capture count and object bytes.
- Implemented Study/Series/Instance projection queries with per-instance capture provenance.
- Accepted and implemented ADR-0029 capture-deletion cascade semantics.

## Design decisions

- Capture directories remain the source of truth. `index.db` is deleted and recreated,
  never migrated.
- `app.db` is preserved through idempotent migrations because jobs, audit records, and
  bookmarks are not derivable from capture artifacts.
- Study projections are recomputed from surviving instance rows after capture deletion.
  A Study spanning multiple captures remains visible and is marked `partial`.
- Capture-scoped bookmarks are deleted with their evidence. Study-level bookmarks remain.
  Future finding/report repositories must expose deleted evidence as `missing_source`; the
  current phase records the cascade contract in the durable audit entry.
- A `.lpcap` discovered in a read-only root is copied into the primary captures root before
  indexing, leaving the source package untouched. Working-form captures in additional roots
  are indexed in place and are not mutated.
- Rebuild comparison uses a deterministic canonical JSON projection snapshot rather than
  SQLite file bytes, which are not a stable cross-run comparison artifact.

## Files added

- `src/lumora_probe/core/storage.py`
- `src/lumora_probe/captures/format.py`
- `src/lumora_probe/captures/repository.py`
- `src/lumora_probe/studies/repository.py`
- `tests/test_phase06_storage_core.py`
- `tests/test_phase06_capture_format.py`
- `tests/test_phase06_capture_repository.py`
- `tests/test_phase06_study_cascade.py`
- `docs/planning/phase-06-capture-format-spec.md`
- `docs/planning/phase-06-completion-report.md`
- `docs/adr/ADR-0029-cascade-semantics.md`

## Files modified

- `docs/adr/README.md`
- `docs/planning/phase-06-capture-format-spec.md`
- `src/lumora_probe/captures/format.py`
- `src/lumora_probe/core/storage.py`
- `src/lumora_probe/captures/repository.py`
- `src/lumora_probe/studies/repository.py`

## Tests and verification

- Full pytest suite: **232 passed, 1 skipped**.
- Ruff lint: passed.
- Ruff format check: passed.
- BasedPyright strict checks for `core` and `shared`: 0 errors, warnings, or notes.
- Import-linter: **7 contracts kept, 0 broken**.
- Package build: `uv build` passed for wheel and source distribution.
- Adversarial coverage includes concurrent readers with one serialized writer, torn trailing
  JSONL recovery, zip-slip rejection, tamper detection, network-filesystem refusal, and
  three-capture projection cascade behavior.

The suite emits existing pydicom warnings from Lite-tool fixtures; no test failed because
of them.

## Known limitations

- Findings and report persistence slices do not exist yet. ADR-0029 defines their future
  `missing_source` behavior and the current cascade audit records zero materialized rows.
- Wire-fidelity raw-byte storage and PDU schema enrichment are deferred to DICOM Networking
  and Capture Engine phases.
- Capture state interruption reasons are not yet populated by a capture writer; lifecycle
  and crash recovery belong to Phase 11.
- Retention selection is implemented; scheduling and deletion orchestration belong to the
  background-operations and Capture Engine workflows.
- SQLite migration versioning currently has one schema version; future app schema changes
  must add explicit migrations while index schema remains rebuildable.

## Follow-up recommendations

Proceed to Phase 07 only after this report is reviewed. Phase 07 should consume the durable
`events.jsonl` path, add the canonical Pydantic event envelope and payload registry, and keep
PDU records outside the event bus as required by ADR-0014.
