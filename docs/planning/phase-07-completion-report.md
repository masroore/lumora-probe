# Phase 07 Completion Report — Event System

**Date:** 2026-07-29
**Status:** Complete

## Completed work

- Added the canonical versioned Pydantic event envelope in `shared/events.py`:
  - UUIDv7 event, correlation, causation, and replay identities.
  - Required `origin` (`observed` or `client-asserted`).
  - UTC wall-clock timestamp, capture-relative monotonic timestamp, and sequencer-assigned sequence.
  - Severity, aggregate identity, producer, payload, and replay provenance.
  - Frozen boundary model with unknown envelope and payload fields preserved.
- Added the payload registry keyed by `(event_name, event_version)`.
  - Known payloads validate through their registered Pydantic model.
  - Unknown future pairs are represented by an explicit opaque payload model.
  - Event names and category changes are validated at registration.
- Added the ten-category event taxonomy and initial catalog registrations, including operational events:
  `EventsDropped`, `ClockAnomalyDetected`, `WarningRaised`, and `ErrorRaised`.
- Added catalog generation from the registry:
  - `scripts/generate_event_catalog.py`
  - `docs/generated/event-catalog-v1.json`
  - Artifact includes envelope schema, payload schemas, categories, origin constraints, replay fields, and unknown-field behavior.
- Added the loop-owned event bus:
  - One asyncio ordering authority.
  - Bounded ingress queue.
  - Thread ingress through `asyncio.run_coroutine_threadsafe` / `loop.call_soon_threadsafe`.
  - Async callbacks awaited; synchronous callbacks invoked inline.
  - Per-capture sequence assignment at publish.
  - Subscriber failure isolation and per-subscriber budget diagnostics.
  - Capture subscriptions are lossless and use an unbounded queue by default.
  - UI subscriptions are bounded and drop oldest; `events_dropped` and `EventsDropped` diagnostics are exposed.
  - Client-asserted events are restricted to Viewer events produced by `web-ui`.
  - Wall/monotonic divergence produces `ClockAnomalyDetected` diagnostics containing both deltas.
  - Runtime setting updates publish redacted `ConfigurationChanged` events through an injected transport-neutral publisher.

## Design decisions

- `category` remains catalog/registry metadata rather than an additional serialized envelope field; this preserves the normative envelope shape while enforcing exactly one category for registered events.
- Sequence scope is supplied by the publisher as `capture_id`; when omitted, the event aggregate ID is the sequence scope. This keeps capture identity out of the canonical envelope and preserves ADR-0017's per-capture ordering contract.
- Unknown event pairs are accepted as opaque payloads so newer captures remain inspectable without silently discarding evidence.
- Capture queue defaults are unbounded because the durable evidence path must not drop. UI queue bounds are explicit because drop-oldest is the documented presentation policy.
- Bus diagnostics are recorded separately from the published event stream. `EventsDropped` diagnostics do not consume capture sequence numbers, so the sequence-gap accounting remains exact.

## Files added

- `src/lumora_probe/shared/events.py`
- `src/lumora_probe/core/bus.py`
- `scripts/generate_event_catalog.py`
- `docs/generated/event-catalog-v1.json`
- `tests/test_phase07_events.py`
- `tests/test_phase07_bus.py`
- `tests/test_phase07_settings_events.py`
- `docs/planning/phase-07-completion-report.md`

## Tests added

- Required origin and UUIDv7 validation.
- UTC timestamp validation.
- Future envelope/payload field round-trip.
- Known payload validation and unknown registry-pair preservation.
- Catalog category coverage and artifact freshness.
- Async subscriber ordering.
- Threaded publisher storm ordering.
- UI drop-oldest accounting against sequence count.
- Capture-path losslessness under UI saturation.
- Client-asserted Viewer quarantine.
- Clock anomaly diagnostics.
- Configuration provenance events and sensitive-value redaction.

## Verification

- Full pytest suite: **243 passed, 1 skipped**.
- Ruff format check: passed.
- Ruff lint: passed.
- BasedPyright strict checks for `core` and `shared`: 0 errors, warnings, or notes.
- Import-linter: **7 contracts kept, 0 broken**.
- Package build: `uv build` passed for wheel and source distribution.

Existing pydicom warnings from Lite-tool fixtures remain unchanged; no test failed because of them.

## Known limitations

- PDU-level records remain outside the event bus and continue to use `pdus.jsonl`, as required by ADR-0014.
- Capture writer lifecycle integration, ring-buffer promotion, and crash recovery remain Phase 11 work.
- Remote transport authentication and a remote publisher endpoint remain later API/runtime work; the local bus ingress is already transport-abstracted.

## Follow-up recommendations

Proceed to Phase 08 after review. REST routes should consume the shared envelope and registry rather than redefining event schemas, and the client-asserted endpoint must reuse the bus Viewer/`web-ui` quarantine rule.
