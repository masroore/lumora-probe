# ADR-0036: Capture Ingress Ownership and Saturation Semantics

- **Status:** Accepted
- **Date:** 2026-08-01
- **Deciders:** Lumora Probe maintainers

## Context

DICOM callbacks execute on pynetdicom association threads while capture persistence and event
ordering are owned by the asyncio process. An unbounded or silently dropping handoff can acknowledge
an object without durable evidence.

## Decision

`CaptureEngine` owns one re-entrant session lock. It serializes session lookup, admission state,
writer append, manifest update, seal, and removal. A session becomes non-accepting under that lock
before stop or interrupt lifecycle publication. Late callbacks refuse the sealed session.

The EventBus remains the only thread boundary. Threaded submissions are bounded by a semaphore and
produce structured not-started, shutting-down, saturated, cancelled, and timed-out outcomes, plus
lock-safe counters. Capture and required DICOM events never drop. PDU/object fidelity remains off
bus; only their summaries/events cross the bus.

C-STORE order is: validate and encode the dataset, durably retain required object evidence, admit
required observed events, then acknowledge. Malformed input maps to `0xC210`, resource exhaustion
or ingress timeout to `0xA700`, and unexpected processing failure to `0xC211`. These are protocol
class outcomes, not application-specific success claims.

Shutdown closes listener admission first, drains active associations and admitted thread work, then
flushes capture/event persistence. Deadline expiry interrupts active sessions. Repeated lifecycle
operations are idempotent.

## Consequences

- Operators can distinguish saturation, timeout, persistence, and late-callback failures.
- Association threads may block for the bounded event-admission timeout; the asyncio loop never
  blocks on a pynetdicom callback.
- Successful C-STORE responses have local durable object evidence and admitted event evidence.
- UI subscriptions retain their documented drop-oldest policy.
