# 03-system-architecture.md

> **Project:** Lumora Probe
>
> **Document:** System Architecture
>
> **Status:** Approved Baseline
>
> **Audience:** Architects, Engineers, AI Coding Agents

---

# 1. Purpose

This document defines the logical architecture of Lumora Probe.

It describes the major subsystems, their responsibilities, communication patterns, and architectural constraints. It intentionally avoids implementation details such as class names, package layouts, or framework-specific code.

---

# 2. Architectural Goals

The architecture shall be:

- Headless-first
- Event-driven
- Modular
- API-first
- Testable
- Extensible
- Observable
- Cross-platform
- Plugin-friendly

---

# 3. High-Level Architecture

```
                 +----------------------+
                 |     CLI Client       |
                 +----------+-----------+
                            |
                 +----------v-----------+
                 |      REST API        |
                 +----------+-----------+
                            |
                 +----------v-----------+
                 |     Application      |
                 |       Services       |
                 +----------+-----------+
                            |
                  Event Bus | Commands
                            |
      +---------------------+----------------------+
      |            |             |                 |
+-----v----+ +-----v-----+ +-----v------+ +--------v------+
| Capture  | | Replay    | | Viewer     | | Reporting     |
| Engine   | | Engine    | | Services   | | Services      |
+-----+----+ +-----+-----+ +-----+------+ +--------+------+
      |            |             |                 |
      +------------+-------------+-----------------+
                           |
                    +------v------+
                    | Storage     |
                    +-------------+

                 Plugins subscribe to the Event Bus.
```

---

# 4. Core Layers

## Presentation Layer

Responsibilities:

- Web UI
- REST API
- CLI
- WebSocket endpoints

No business logic should exist in this layer.

---

## Application Layer

Coordinates workflows.

Examples:

- Open capture
- Analyze study
- Replay session
- Export report

---

## Domain Layer

Contains business concepts.

Examples:

- Association
- Study
- Series
- Instance
- Capture
- Event
- Timeline
- Report

Framework independent.

---

## Infrastructure Layer

Provides:

- SQLite
- Filesystem
- Logging
- HTTP
- Plugin loading
- DICOM networking

---

# 5. Event Bus

The Event Bus is the heart of Lumora Probe.

Every significant activity produces an immutable event.

Examples:

- AssociationStarted
- AssociationAccepted
- CStoreReceived
- DatasetParsed
- ImageDecoded
- ImageDisplayed
- WarningRaised
- ErrorRaised
- ReplayStarted

Consumers never communicate directly when events are sufficient.

---

# 6. Communication Style

Preferred:

Publisher → Event Bus → Subscribers

Avoid:

Module → Module → Module chains.

---

# 7. Headless Design

All functionality must be accessible without the Web UI.

The UI is a consumer of backend services, not the owner of business logic.

Future interfaces may include:

- Desktop UI
- Terminal UI
- Automation scripts
- CI pipelines

without redesigning the application.

---

# 8. Plugin Architecture

Plugins interact through stable extension points.

Plugins must not depend on internal implementation details.

Plugins may:

- Subscribe to events
- Add analyzers
- Generate reports
- Provide vendor diagnostics
- Register commands

---

# 9. Storage Strategy

Separate concerns:

- Configuration
- Captures
- Reports
- Logs
- Application database

Captured evidence should remain portable.

---

# 10. API Strategy

The REST API exposes application capabilities.

The Web UI should consume the same public API whenever practical.

Real-time updates are delivered via WebSockets.

---

# 11. Concurrency

Long-running operations should execute asynchronously.

Examples:

- Capture import
- Replay
- Report generation
- Metadata indexing

The UI should remain responsive.

---

# 12. Error Handling

Errors should:

- be structured
- include context
- generate events
- be logged
- surface meaningful remediation guidance

Silent failures are prohibited.

---

# 13. Observability

Every subsystem should emit:

- Logs
- Metrics
- Events

These are first-class architectural concepts rather than afterthoughts.

---

# 14. Architectural Constraints

The following decisions are fixed unless superseded by an ADR:

- Python backend
- FastAPI service layer
- HTMX-based web interface
- Event-driven communication
- Headless architecture
- Plugin model
- Local-first deployment

---

# 15. Quality Attributes

Priority order:

1. Correctness
2. Reliability
3. Observability
4. Maintainability
5. Extensibility
6. Performance
7. Developer Experience

Premature optimization should not compromise maintainability.

---

# 16. Future Evolution

The architecture should accommodate future support for:

- DICOMweb
- HL7
- FHIR
- Distributed collectors
- Remote agents
- Cloud deployments

without fundamental redesign.

---

# 17. Summary

The defining architectural characteristics of Lumora Probe are:

- Headless-first
- Event-driven
- Modular
- API-centric
- Plugin-oriented
- Observability-focused

Every implementation decision should reinforce these principles.
