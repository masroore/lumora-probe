# 19-glossary.md

> **Project:** Lumora Probe
>
> **Document:** Glossary
>
> **Status:** Architecture Baseline (reconciled Phase 18 / T-18-03-01)
>
> **Audience:** All Contributors, Architects, Engineers, QA, Plugin Developers, Claude Code, Codex

---

# 1. Purpose

This glossary defines the canonical terminology used throughout the Lumora Probe documentation.

All architecture documents, specifications, code, tests, and documentation should use these terms consistently.
Where this glossary and an accepted ADR disagree, the ADR wins and this glossary must be updated.

---

# 2. Naming Principles

Terminology should be:

- Consistent
- Unambiguous
- Technology-neutral where practical
- Shared across documentation and code

---

# 3. Domain Terms

| Term | Definition |
|------|------------|
| Study | A **capture-derived projection** over observed DICOM Study Instance UIDs (ADR-0013). Not a top-level aggregate and not a PACS archive object. |
| Series | A **capture-derived projection** grouping Instances under a Study Instance UID and Series Instance UID (ADR-0013). |
| Instance | A **capture-derived projection** for one SOP Instance UID as observed in one or more captures (ADR-0013). |
| Dataset | A collection of DICOM attributes. |
| Metadata | Non-pixel descriptive information associated with DICOM objects. |
| Capture | Recorded engineering evidence for investigation or replay: a self-contained directory under the data root (ADR-0004). Distinct from `.lpcap`, which is the interchange zip of that directory. |
| `.lpcap` | Interchange form of a Capture: the capture directory zipped with deflate. Dropping one into `captures/` makes it appear. |
| Ring buffer | Always-on, bounded rolling evidence buffer with retention and byte cap (ADR-0008, ADR-0030). Distinct from a Capture. |
| Promotion | Copying a time window out of the ring buffer into a permanent Capture / `.lpcap` (ADR-0008). |
| Fidelity tier | Capture stream completeness: `events` → `protocol` → `wire` (ADR-0005). Replay refuses modes the capture cannot support. |
| Replay | Three meanings (ADR-0005); two ship in v1: **event replay** (offline into the bus) and **protocol replay** (SCU against a real target). Byte-exact / mock-peer replay is deferred. |
| Analysis | Automated or manual interpretation of engineering evidence. |
| Condition | Deterministic **observed** fact with a stable condition ID (`LP-XXX-NNN`), emitted as a warning or error. Physically separate from Findings (ADR-0018). Alias: **Diagnostic Condition**. |
| Diagnostic Condition | Alias of Condition; prefer Condition in new writing. |
| Finding | Versioned rule-derived **inference** stored under a capture's `analysis/` directory, never in `events.jsonl` (ADR-0018). Regenerable. |
| Condition ID | Stable `LP-XXX-NNN` identifier; `XXX` is a three-letter namespace and `NNN` is a never-reused sequence from `001` through `999`. |
| Association pair | The calling and called Application Entity titles (and related network endpoints) that bound one DICOM association negotiation. |
| Domain event | Canonical envelope written to `events.jsonl`. Distinct from a **protocol trace** PDU record in `pdus.jsonl`. |
| Protocol trace | PDU-level structural/timing record in `pdus.jsonl`; present at fidelity ≥ `protocol`. Never published as a domain event to improve a metric. |
| Redaction | Honest, partial tag-level or object-dropping handover preparation (ADR-0026). **Not** anonymization, de-identification, or PS3.15 conformance. |
| De-identification | Standards claim (e.g. PS3.15) that Lumora Probe **does not** make. Prefer redaction or object-dropping language. |
| Report | Generated investigation output. |

### Capture Summary Report

A structured JSON document (`CaptureSummaryReport`) exported from a capture directory. Contains
aggregated decode timing evidence (`CaptureDecodeTiming`) per instance, computed from observed
`ImageDecoded` events only. Client-asserted events are excluded per ADR-0016 quarantine. Phase 15
owns full report generation; this is the minimal Phase 13 evidence export.

---

# 4. DICOM Terms

Common terminology includes:

- AE Title
- Association
- DIMSE
- SOP Class
- SOP Instance UID
- Study Instance UID
- Series Instance UID
- Transfer Syntax
- Presentation Context
- C-ECHO
- C-FIND
- C-MOVE
- C-GET
- C-STORE

Use standard DICOM terminology whenever applicable.

---

# 5. Architectural Terms

| Term | Definition |
|------|------------|
| Aggregate | Primary consistency boundary in the domain model. |
| Entity | Object with identity. |
| Value Object | Immutable object defined by its value. |
| Repository | Persistence abstraction for aggregates. |
| Domain Event | Immutable record describing something that occurred (see Domain Terms). |
| Event Bus | Infrastructure responsible for distributing events. |
| Canonical event log | Append-only `events.jsonl` inside a Capture directory — the authoritative event store replacement (ADR-0004). |
| Index | Rebuildable projection store (`index.db`); droppable when the capture directory disagrees (ADR-0023). |

---

# 6. API Terms

- Resource
- Endpoint
- Request
- Response
- Pagination
- Filter
- Version
- Authentication
- Authorization

REST terminology should align with the REST API specification.

---

# 7. WebSocket Terms

- Connection
- Subscription
- Channel
- Topic
- Heartbeat
- Message
- Event Stream

---

# 8. Storage Terms

| Term | Definition |
|------|------------|
| Capture directory | Authoritative evidence layout for one Capture (ADR-0004). Replaces the baseline “Event Store” notion. |
| Metadata Store | Historical baseline term; prefer projection/index vocabulary for Study/Series/Instance rows. |
| Event Store | **Deprecated baseline term.** Use capture directory + canonical event log (`events.jsonl`) and rebuildable `index.db`. |
| Repository | Persistence abstraction for aggregates or projections. |
| Archive | Not a Lumora Probe product role; the Charter forbids becoming a PACS archive. |
| Cache | Bounded, discardable acceleration (e.g. decode cache); never authoritative evidence. |
| Backup | Operator responsibility: preserve `app.db` and Capture directories per retention obligations; `index.db` is rebuildable. |
| Restore | Reconstructing operator-backed state; interrupted jobs are never auto-resumed (ADR-0023). |
| Retention | Ring-buffer time/byte limits or operator capture retention policy. |

---

# 9. Plugin Terms

- **Plugin** — trusted in-process Python extension loaded through the public SDK.
- **Extension** — optional code that contributes behavior through a documented hook.
- **Manifest** — plugin metadata declaring identity, SDK range, entry point, hooks, and
  capabilities for structural validation and operator disclosure.
- **Capability** — declared plugin intent; not an enforced permission boundary in v1.
- **Hook** — versioned pluggy extension point receiving contracts DTOs.
- **SDK** — public `lumora_probe.plugins.api` and `contracts` surface for plugin authors.
- **Compatibility** — SDK-major range accepted by the loader before activation.

---

# 10. Observability Terms

- Log
- Metric
- Trace
- Health Check
- Correlation ID
- Causation ID
- Dashboard
- Alert

---

# 11. Security Terms

- Authentication
- Authorization
- Least Privilege
- PHI
- Encryption
- Audit Log
- Secret
- Trust Boundary

---

# 12. Development Terms

- ADR
- PRD
- CI
- CD
- Unit Test
- Integration Test
- End-to-End Test
- Static Analysis
- Code Review

---

# 13. Acronyms

| Acronym | Meaning |
|----------|---------|
| ADR | Architecture Decision Record |
| AE | Application Entity |
| API | Application Programming Interface |
| CI | Continuous Integration |
| DDD | Domain-Driven Design |
| DICOM | Digital Imaging and Communications in Medicine |
| DIMSE | DICOM Message Service Element |
| GA | General Availability |
| HL7 | Health Level Seven |
| LTS | Long-Term Support |
| PACS | Picture Archiving and Communication System |
| PHI | Protected Health Information |
| PRD | Product Requirements Document |
| QA | Quality Assurance |
| REST | Representational State Transfer |
| SDK | Software Development Kit |
| SOP | Service-Object Pair |
| UID | Unique Identifier |
| UX | User Experience |
| WebSocket | Full-duplex communication protocol |

---

# 14. Naming Conventions

General conventions:

- PascalCase for domain events
- snake_case where defined by implementation standards
- Plural resource names for REST APIs
- Singular aggregate names
- Clear, descriptive identifiers

Refer to the Development Guidelines for language-specific conventions.

---

# 15. References

Related documents:

- 03-system-architecture.md
- 06-event-driven-architecture.md
- 07-data-model.md
- 08-rest-api-specification.md
- 09-websocket-specification.md
- 10-plugin-sdk.md
- 18-development-guidelines.md
- ADR-0004, ADR-0005, ADR-0008, ADR-0013, ADR-0018, ADR-0023, ADR-0026
