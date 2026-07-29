# Phase 11 Completion Report — Capture Engine

**Status:** Complete
**Date:** 2026-07-29
**Milestone:** M9 — Durable capture and recovery

## Completed work

- Added an always-on bounded ring buffer with 30-minute / 2 GiB defaults, byte and age
  eviction, optional durable `records.jsonl` backing, and retention status reporting.
- Added the `ring_buffer_events_only` runtime setting and `LUMORA_RING_BUFFER_EVENTS_ONLY`
  environment source.
- Added explicit capture sessions using the Capture aggregate lifecycle, lifecycle event
  publication, manifest clock anchors, client-asserted event counts, and sealed manifests.
- Added retroactive promotion with digest-addressed object copying, PDU/event stream copying,
  requested/actual window provenance, source aggregate IDs, fidelity derivation, and partial
  aggregate marking.
- Added PDU and C-STORE sink adapters so DICOM observations can feed the ring buffer and active
  sessions without putting PDU records on the event bus.
- Added capture retention exposure at `GET /api/v1/captures/ring-buffer`.
- Added durable rebuild recovery for torn trailing event lines and active capture manifests;
  interrupted reasons are preserved in the derived index.
- Added shutdown-deadline interruption handling to the core lifecycle manager.
- Ratified Phase 11 volume and retention budgets in ADR-0030.

## Design decisions

- Capture service APIs require injected clock and ID sources. This preserves ADR-0022 and the
  import-linter boundary; capture code does not import `time` or `uuid` transitively.
- Event persistence uses `EventEnvelope.to_json_bytes()` rather than a second serializer.
- Ring-buffer records are bounded by raw evidence bytes. Durable ring metadata uses a small
  JSONL wrapper and base64 only for persistence; promotion writes the original raw evidence.
- Raw `wire` fidelity is refused. The phase does not claim a capability not delivered by the
  current pynetdicom integration.
- `index.db` remains derived. Sealed captures are indexed through an injected repository sink;
  recovery always treats the capture directory as authoritative.

## Files added

- `src/lumora_probe/captures/service.py` (implemented capture engine and ring buffer)
- `tests/test_phase11_capture.py`
- `tests/test_phase11_budgets.py`
- `docs/capture-engine.md`
- `docs/adr/ADR-0030-ratified-performance-budgets.md`

## Files modified

- `src/lumora_probe/captures/format.py`
- `src/lumora_probe/captures/repository.py`
- `src/lumora_probe/core/lifecycle.py`
- `src/lumora_probe/settings/runtime.py`
- `src/lumora_probe/shared/events.py`
- `src/lumora_probe/web/api.py`
- `src/lumora_probe/web/capture_routes.py`
- Generated event/OpenAPI artifacts and Phase 06/08/core test coverage.

## Tests and verification

- Full pytest suite: **309 passed, 1 skipped**.
- Ring capacity, age expiry, durable reload, events-only filtering, explicit sessions,
  promotion, PDU/object sinks, torn-line recovery, and active-manifest recovery are covered.
- `lint-imports --no-cache`: 7 contracts kept, 0 broken.
- Ruff check and format checks pass for changed Python files.
- Representative synthetic workload: 5,000 domain events plus 16,000 PDU records for 500
  instances; 21,000 retained records used 520,380 bytes locally. Ratified thresholds are in
  ADR-0030.
- Ruff check and format check: passed.
- BasedPyright (`core`, `shared`): 0 errors, warnings, or notes.
- Import-linter: 7 contracts kept, 0 broken.
- Asset drift check and wheel/source distribution build: passed after `npm ci`.

## Known limitations

- The application composition accepts an injected `CaptureEngine`; deployment bootstrap must
  construct it with `DataPaths`, the live `EventBus`, and injected clock/ID sources.
- Background promotion job audit/cancellation remains a Phase 12/ADR-0023 integration task;
  the synchronous promotion path is complete and can be run through an async worker.
- Raw wire fidelity and byte-exact replay remain deferred as documented by ADR-0005 and the
  Phase 10 report.
- Full subprocess kill/SIGTERM harness remains environment-sensitive; component recovery and
  lifecycle deadline tests cover the deterministic recovery paths.

## Follow-up recommendations

- Wire the capture engine into the production DICOM listener factory with `engine` as both
  PDU trace sink and C-STORE sink.
- Add durable promotion operation records when the background operation executor is expanded.
- Add an opt-in subprocess durability suite to CI on platforms with stable signal semantics.
