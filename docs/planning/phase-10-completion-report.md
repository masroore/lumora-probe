# Phase 10 Completion Report — DICOM Networking

**Status:** Complete
**Date:** 2026-07-29
**Phase:** 10 — DICOM Networking
**Milestone:** M8 — Traffic Observable

## Completed work

- Added a non-privileged pynetdicom SCP listener with default port `11112`.
- Added independent DICOM bind configuration (`dicom_bind_host`) with the existing
  unauthenticated-network gate applied to both HTTP and DICOM planes.
- Added async SCU verification with negotiated C-ECHO and clean release.
- Added association lifecycle audit records for every requested, accepted, rejected,
  released, and aborted association, including calling AE and source endpoint.
- Added optional calling-AE allowlisting; default remains accept-all.
- Added thread-safe event-bus ingress for association lifecycle and DIMSE events. Association
  callbacks do not call the asyncio bus directly.
- Added explicit relay modes:
  - pass-through (default; requires an upstream peer at operation time);
  - permissive standalone (always labelled);
  - destination-AE interception configuration seam.
- Added C-ECHO and C-STORE inline forwarding with upstream status propagation and per-operation
  enrichment events.
- Added C-FIND, C-GET, and C-MOVE forwarding seams. C-FIND responses and C-MOVE progress are
  relayed; C-GET datasets remain on the same association.
- Added service-agnostic N-service observation. Unrecognized DIMSE commands produce
  `UnrecognizedDimseObserved` and a DICOM failure response without aborting the association.
- Added byte-faithful relay primitive that forwards malformed bytes unchanged and emits a
  structural diagnostic instead of repairing or normalizing the input.
- Added off-bus PDU tracing with compact JSONL records, PDU type/length, PDV boundaries,
  presentation-context IDs, direction, timestamp, and digest metadata for direct relay use.
- Added DIMSE summary fields for PDU count, bytes, first/last timestamps, and maximum inter-PDU
  gap. PDU trace rows never enter the event bus.
- Registered Phase 10 event contracts and regenerated `docs/generated/event-catalog-v1.json`.
- Added public association API and contract re-export seams while preserving the repository's
  empty `__all__` boundary convention.

## Design decisions

- The listener is an async lifecycle facade over pynetdicom's thread-per-association runtime.
  Blocking SCU operations execute in worker threads; association callbacks use the injected
  thread-safe ingress contract.
- Clock and identity implementations remain outside the associations slice. The slice accepts
  local protocols so import-linter's `time`/`uuid` boundary remains intact.
- Pass-through and permissive standalone are distinct modes. Missing upstream in pass-through is
  an explicit refusal path, not silent fallback to standalone.
- Valid C-STORE forwarding uses pydicom/pynetdicom dataset encoding. Raw malformed-byte
  forwarding is isolated in `ByteFaithfulRelay`; the high-level DIMSE enrichment path never
  claims to repair malformed traffic.
- PDU telemetry is deliberately a side stream, in line with ADR-0014. It is not represented as
  event envelopes and cannot consume event-bus sequencing capacity.

## Files added

- `src/lumora_probe/associations/network.py`
- `src/lumora_probe/associations/relay.py`
- `tests/test_phase10_network.py`
- `docs/planning/phase-10-completion-report.md`

## Files modified

- `src/lumora_probe/associations/__init__.py`
- `src/lumora_probe/associations/api.py`
- `src/lumora_probe/associations/contracts.py`
- `src/lumora_probe/core/config.py`
- `src/lumora_probe/shared/events.py`
- `docs/generated/event-catalog-v1.json`
- `tests/test_core_infrastructure.py`
- `src/probe_lite/__main__.py`
- `src/sender_lite/__main__.py`
- `README.md`

## Tests added

- Listener bind, health, non-privileged port, and AE-title validation.
- Real loopback C-ECHO against pynetdicom.
- Thread-safe lifecycle event ingress and calling-AE/source-IP audit logging.
- Calling-AE allowlist acceptance/rejection.
- Pass-through context mirroring and explicit relay mode semantics.
- Byte-faithful malformed PDU forwarding and diagnostic output.
- Real loopback C-ECHO and C-STORE inline relay.
- Real loopback C-FIND response relay and completion summary.
- Unrecognized DIMSE observation without association abort.
- PDU trace side-stream and bus exclusion.
- Event catalog registration for Phase 10 contracts.
- Independent DICOM bind host configuration and exposure gate.

## Verification

- Full pytest suite: **301 passed, 1 skipped**.
- Ruff format check: passed.
- Ruff lint: passed.
- BasedPyright (`core`, `shared`): passed with 0 errors, warnings, and notes.
- BasedPyright association implementation: passed with 0 errors, warnings, and notes.
- Import-linter: **7 contracts kept, 0 broken**.
- Asset drift check: passed after `npm ci`.
- Wheel and source distribution build: passed.

## Known limitations

- Full raw PDU socket splicing is intentionally isolated behind `ByteFaithfulRelay`; pynetdicom's
  high-level intervention handlers decode valid DIMSE requests before enrichment. A future wire
  fidelity implementation must preserve the current no-repair boundary rather than introducing
  parse-and-re-encode fallback.
- Destination-AE interception is a labelled configuration seam; automatic PACS destination
  discovery remains outside this phase.
- C-MOVE sub-operations remain out-of-band by DICOM design. Probe relays command/progress and
  does not claim to observe PACS-to-destination C-STORE objects.
- Durable capture promotion, ring buffering, crash recovery, and manifest fidelity are Phase 11.
- Authentication/RBAC remains deferred per ADR-0009.

## Follow-up recommendations

Proceed to Phase 11 only after wiring the listener/relay event ingress and PDU writer into the
capture service. Phase 11 should ratify event/PDU/ring-buffer budgets against representative
synthetic studies and add kill-mid-capture recovery around the new side stream.
