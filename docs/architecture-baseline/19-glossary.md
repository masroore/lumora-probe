# 19-glossary.md

> **Project:** Lumora Probe
>
> **Document:** Glossary
>
> **Status:** Architecture Baseline
>
> **Audience:** All Contributors, Architects, Engineers, QA, Plugin Developers, Claude Code, Codex

---

# 1. Purpose

This glossary defines the canonical terminology used throughout the Lumora Probe documentation.

All architecture documents, specifications, code, tests, and documentation should use these terms consistently.

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
| Study | A DICOM Study consisting of one or more Series. |
| Series | A logical grouping of DICOM Instances. |
| Instance | A DICOM SOP Instance. |
| Dataset | A collection of DICOM attributes. |
| Metadata | Non-pixel descriptive information associated with DICOM objects. |
| Capture | Recorded engineering evidence for investigation or replay. |
| Replay | Re-execution of captured events for analysis. |
| Analysis | Automated or manual interpretation of engineering evidence. |
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
| Domain Event | Immutable record describing something that occurred. |
| Event Bus | Infrastructure responsible for distributing events. |

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

- Metadata Store
- Event Store
- Repository
- Archive
- Cache
- Backup
- Restore
- Retention

---

# 9. Plugin Terms

- Plugin
- Extension
- Manifest
- Capability
- Hook
- SDK
- Compatibility

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
