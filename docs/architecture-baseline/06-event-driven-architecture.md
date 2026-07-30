# 06-event-driven-architecture.md

> Project: **Lumora Probe**  
> Status: **Normative Specification**  
> Audience: Architects, Engineers, QA, Plugin Authors, AI Coding Agents

---

# 1. Purpose

This document defines the event-driven architecture used throughout Lumora Probe. It is a normative implementation specification. Unless superseded by an ADR, all services, plugins, APIs, and user interfaces SHALL conform to this document.

RFC 2119 terminology is used:

- **MUST / SHALL** – mandatory
- **SHOULD** – recommended
- **MAY** – optional

---

# 2. Objectives

The event architecture SHALL:

- Decouple modules
- Preserve engineering evidence
- Enable replay
- Support plugins
- Support observability
- Provide deterministic debugging
- Maintain backward compatibility

Non-goals:

- Distributed message broker
- Event sourcing for business persistence
- Exactly-once distributed delivery

---

# 3. Core Principles

1. Events are immutable.
2. Every meaningful state transition emits an event.
3. Events describe facts, never commands.
4. Commands request work; events describe completed observations.
5. Producers never know subscribers.
6. Subscribers must tolerate unknown future fields.

---

# 4. Terminology

| Term | Definition |
|------|------------|
| Event | Immutable record describing something that happened |
| Publisher | Component producing an event |
| Subscriber | Component consuming an event |
| Aggregate | Logical owner of a lifecycle (Association, Capture, Replay, etc.) |
| Correlation ID | Links related events |
| Causation ID | Parent event that caused the current event |

---

# 5. Event Categories

Every event belongs to exactly one category.

| Category | Examples |
|-----------|----------|
| Association | AssociationStarted, AssociationReleased |
| DIMSE | CStoreReceived, CFindCompleted |
| Dataset | DatasetLoaded |
| Viewer | ImageDisplayed |
| Capture | CaptureStarted |
| Replay | ReplayFinished |
| Analysis | AnalysisCompleted |
| Reporting | ReportProgressed, ReportGenerated |
| Plugin | PluginLoaded |
| System | ApplicationStarted |

---

# 6. Canonical Event Envelope

Every event SHALL use the same envelope.

```json
{
  "event_id": "uuidv7",
  "event_name": "AssociationStarted",
  "event_version": 1,
  "occurred_at": "2026-01-01T12:00:00Z",
  "correlation_id": "uuidv7",
  "causation_id": "uuidv7|null",
  "aggregate_type": "Association",
  "aggregate_id": "assoc-001",
  "producer": "association-manager",
  "severity": "info",
  "payload": {}
}
```

Required fields:

- event_id
- event_name
- event_version
- occurred_at
- correlation_id
- aggregate_type
- aggregate_id
- producer
- payload

---

# 7. Event Naming

Rules:

- PascalCase
- Past tense
- Singular
- No abbreviations except accepted DICOM terms

Examples:

- AssociationStarted
- CStoreReceived
- DatasetParsed
- ImageDisplayed

Avoid:

- StartAssociation
- ParseDataset
- DoReplay

---

# 8. Versioning

Every event includes an integer event_version.

Rules:

- Additive fields increment minor schema documentation only.
- Breaking payload changes require a new event version.
- Subscribers MUST ignore unknown properties.
- Deprecated fields remain available for one major release.

---

# 9. Ordering

Ordering is guaranteed only:

- within a single aggregate
- within one capture session

Global ordering is NOT guaranteed.

Consumers SHALL rely on:

- occurred_at
- correlation_id
- aggregate_id

instead of arrival order.

---

# 10. Delivery Guarantees

Baseline guarantees:

- At-least-once delivery
- Best-effort ordering
- Idempotent subscribers
- Durable capture persistence

Subscribers SHALL safely process duplicate events.

---

# 11. Correlation

A correlation_id identifies one logical investigation.

Example:

AssociationStarted
→ CStoreReceived
→ DatasetParsed
→ ImageDisplayed
→ AnalysisCompleted

All share the same correlation_id.

---

# 12. Causation

Every derived event SHOULD reference the event that caused it.

Example:

CaptureStarted
↓
DatasetParsed
↓
MetadataExtracted
↓
AnalysisCompleted

---

# 13. Publisher Contract

Publishers SHALL:

- validate payload
- timestamp events
- assign identifiers
- never mutate published events
- publish only completed facts

---

# 14. Subscriber Contract

Subscribers SHALL:

- be idempotent
- ignore unknown fields
- avoid blocking
- emit ErrorRaised on failures
- avoid modifying original events

---

# 15. Event Bus Requirements

The event bus SHALL:

- dispatch synchronously or asynchronously
- preserve aggregate ordering
- support multiple subscribers
- isolate subscriber failures
- expose diagnostics

---

# 16. Persistence

Captured events SHALL be persisted exactly as published.

Replay SHALL reconstruct behavior from persisted events without modifying payloads.

---

# 17. Plugin Integration

Plugins MAY:

- publish custom events
- subscribe to built-in events
- enrich analysis
- generate reports

Plugins SHALL NOT modify previously published events.

---

# 18. Reliability

The implementation SHALL provide:

- duplicate detection
- structured logging
- retry with exponential backoff where appropriate
- dead-letter recording for unrecoverable subscriber failures

---

# 19. Observability

Every event SHALL generate:

- structured log entry
- tracing metadata
- metrics (publish count, latency, failures)

---

# 20. Security

Events SHALL NOT expose:

- credentials
- API secrets
- authentication tokens
- decrypted protected data

Sensitive values SHALL be redacted before publication.

---

# 21. Testing Requirements

Every publisher requires:

- schema validation tests
- ordering tests
- serialization tests

Every subscriber requires:

- idempotency tests
- duplicate delivery tests
- malformed payload tests

---

# 22. Acceptance Criteria

The implementation is compliant when:

- Every state transition emits a documented event.
- All events conform to the canonical envelope.
- Events remain immutable.
- Replay reproduces persisted event streams.
- Subscribers tolerate duplicate delivery.
- Plugins interoperate through documented contracts only.
- All event schemas are versioned and validated.

---

# Appendix A — Initial Core Event Catalog

## Association

- AssociationStarted
- AssociationAccepted
- AssociationRejected
- AssociationReleased
- AssociationAborted

## DIMSE

- CEchoReceived
- CStoreReceived
- CFindReceived
- CMoveRequested
- CGetRequested

## Dataset

- DatasetLoaded
- DatasetParsed
- MetadataExtracted

## Viewer

- ImageDisplayed
- WindowLevelChanged
- CineStarted

## Capture

- CaptureStarted
- CaptureStopped
- CaptureCompleted

## Replay

- ReplayStarted
- ReplayPaused
- ReplayCompleted

## Reporting

- ReportProgressed
- ReportGenerated
- ReportExported

## System

- ApplicationStarted
- ApplicationStopped
- ErrorRaised
- WarningRaised

---

This specification forms the architectural contract for every subsystem within Lumora Probe. Future event types SHALL extend this document without violating the compatibility rules defined above.
