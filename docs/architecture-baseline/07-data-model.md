# 07-data-model.md

> **Project:** Lumora Probe
>
> **Document:** Data Model
>
> **Status:** Architecture Baseline
>
> **Audience:** Architects, Engineers, QA, Plugin Developers, Claude Code, Codex

---

# 1. Purpose

This document defines the canonical domain model for Lumora Probe.

Its purpose is to establish the conceptual model, aggregate boundaries, ownership rules, identities, and relationships used throughout the application.

This document intentionally focuses on the **domain model**, not the physical database schema.

Implementation details such as SQL tables, indexes, repository implementations, migrations, and serialization optimizations are intentionally deferred to later technical design documents.

---

# 2. Objectives

The data model SHALL:

- Represent the domain consistently
- Be independent of storage technology
- Support event-driven architecture
- Support replayable workflows
- Support plugin extensibility
- Minimize coupling
- Preserve engineering evidence
- Enable future evolution

The model SHALL prioritize correctness and maintainability over premature optimization.

---

# 3. Design Principles

The Lumora Probe data model follows these principles:

- Domain-Driven Design (DDD)
- Aggregate-oriented modeling
- Rich domain concepts
- Explicit ownership
- Immutable value objects where practical
- Event-driven consistency
- Storage independence
- Technology-neutral design

Business concepts SHALL not depend on persistence technologies.

---

# 4. Domain Overview

```
Application
│
├── Association
├── Capture
├── Replay
├── Study
│   ├── Series
│   │   └── Instance
├── Analysis
├── Report
├── Plugin
└── Configuration
```

Each aggregate owns its lifecycle and publishes domain events.

---

# 5. Aggregate Catalog

| Aggregate | Purpose |
|------------|---------|
| Association | Represents a DICOM association lifecycle |
| Capture | Represents an engineering capture session |
| Replay | Represents replay execution |
| Study | Represents a DICOM study hierarchy |
| Analysis | Represents generated diagnostic findings |
| Report | Represents exported investigation artifacts |
| Plugin | Represents installed extensions |
| Configuration | Represents application configuration |

---

# 6. Aggregate Responsibilities

For every aggregate the implementation SHALL define:

- Purpose
- Responsibilities
- Lifecycle
- Identity
- Relationships
- Published Events
- Consumed Events
- Repository
- Validation Rules

---

# 7. Entity Catalog

Expected entities include:

- Study
- Series
- Instance
- Association
- Capture
- Replay
- Analysis
- Report
- Plugin
- Configuration

Each entity should define:

- Purpose
- Identity
- Required metadata
- Relationships
- Validation
- Persistence guidance

---

# 8. Value Objects

Typical immutable value objects:

- DICOM UID
- AE Title
- Network Endpoint
- Presentation Context
- Transfer Syntax
- SOP Class UID
- Timestamp
- Duration
- File Path
- DICOM Tag
- Pixel Dimensions
- Window Level
- Window Width

---

# 9. Identity Strategy

The model supports:

- UUIDv7 internal identifiers
- Native DICOM UIDs
- Correlation IDs
- Causation IDs
- Stable aggregate identities

---

# 10. Relationships

```
Study
 └── Series
      └── Instance

Capture
 ├── Events
 ├── Logs
 └── Analysis

Replay
 └── Capture
```

Ownership, lifecycle, and cascade behavior shall be explicitly defined.

---

# 11. Ownership Rules

Every entity SHALL have a single owning aggregate.

Ownership determines:

- Lifecycle
- Persistence
- Validation
- Event publication

---

# 12. Lifecycle Models

Typical aggregate state machines:

## Association

Requested → Negotiating → Established → Released → Archived

## Capture

Created → Running → Stopping → Completed → Archived

## Replay

Pending → Running → Paused → Completed → Archived

---

# 13. Persistence Guidance

Persistence is an implementation concern.

The domain model should remain independent from:

- SQLite
- JSON
- Filesystem
- ORM implementation

Repositories isolate persistence from domain behavior.

---

# 14. Repository Guidance

Typical repositories:

- StudyRepository
- CaptureRepository
- ReplayRepository
- AnalysisRepository
- ReportRepository

Repositories should implement persistence, retrieval, search, and transaction boundaries without containing business logic.

---

# 15. Validation

Validation should include:

- Domain validation
- Persistence validation
- Import validation
- Replay validation
- Configuration validation

---

# 16. Event Integration

Every aggregate may publish and consume events.

Event contracts SHALL comply with:

- `06-event-driven-architecture.md`

---

# 17. Serialization

Supported serialization targets:

- REST
- JSON
- WebSocket
- Report Export
- Plugin SDK

---

# 18. Versioning

The model should support:

- Schema evolution
- Event compatibility
- Backward compatibility
- Migration planning

---

# 19. Performance Guidance

Implementation should support:

- Lazy loading
- Streaming
- Incremental processing
- Large studies
- Large capture sessions

---

# 20. Extensibility

Future aggregates may include:

- DICOMweb
- HL7
- FHIR
- Remote Agents
- Fleet Management
- Rule Engine
- Notification Service

---

# 21. Security

The model should support:

- PHI protection
- Redaction
- Audit trails
- Encryption
- Access control

---

# 22. Acceptance Criteria

The architecture is complete when:

- Aggregate boundaries are defined.
- Ownership rules are documented.
- Relationships are established.
- Identity strategy is documented.
- Lifecycle models are defined.
- Repository guidance is documented.
- Validation responsibilities are identified.
- Event interactions are documented.

---

# 23. Open Design Questions

To be resolved during implementation:

- Physical schema
- Index strategy
- Repository interfaces
- Transaction boundaries
- Migration tooling
- Caching strategy
- Concurrency model
- Performance optimizations

---

# 24. References

- 00-project-charter.md
- 01-product-vision.md
- 02-product-requirements-document.md
- 03-system-architecture.md
- 04-technology-stack.md
- 05-system-modules.md
- 06-event-driven-architecture.md
