# 05-system-modules.md

> **Project:** Lumora Probe
>
> **Document:** System Modules
>
> **Status:** Approved Baseline
>
> **Audience:** Architects, Engineers, AI Coding Agents

---

# 1. Purpose

This document decomposes Lumora Probe into logical modules (bounded contexts).

Each module has clearly defined responsibilities, public interfaces, published events, consumed events, dependencies, and explicit non-responsibilities.

A module should own one primary concern.

---

# 2. Module Design Principles

Every module should:

- Have a single primary responsibility
- Be independently testable
- Communicate primarily through events
- Minimize direct dependencies
- Hide implementation details
- Expose stable interfaces

---

# 3. Module Overview

| Module | Purpose |
|---------|---------|
| Dashboard | Operational overview |
| Live Monitor | Observe active DICOM activity |
| Association Manager | Track DICOM associations |
| Capture Engine | Record engineering evidence |
| Replay Engine | Replay captured sessions |
| Study Browser | Navigate studies |
| DICOM Viewer | Render images |
| Metadata Inspector | Inspect datasets |
| Transfer Analysis | Analyze protocol performance |
| Event Timeline | Correlate lifecycle events |
| Logging | Structured logging |
| Reporting | Export investigation results |
| Plugin Host | Extension framework |
| Settings | Configuration |
| REST API | External interface |
| Storage | Persistence |

---

# 4. Dashboard

## Responsibilities

- System overview
- Recent activity
- Health indicators
- Key metrics

## Publishes

- DashboardRefreshed

## Consumes

- All high-level operational events

## Does Not

- Perform diagnostics
- Store data

---

# 5. Live Monitor

## Responsibilities

- Display active associations
- Live throughput
- Live event stream

## Publishes

- LiveSessionOpened

## Consumes

- Association events
- DIMSE events
- Transfer events

---

# 6. Association Manager

## Responsibilities

- Track association lifecycle
- Negotiation details
- Presentation contexts
- Connection state

Publishes:

- AssociationStarted
- AssociationAccepted
- AssociationReleased
- AssociationAborted

---

# 7. Capture Engine

## Responsibilities

- Capture protocol events
- Persist engineering evidence
- Package captures

Publishes:

- CaptureStarted
- CaptureCompleted

Consumes:

- All observable events

---

# 8. Replay Engine

## Responsibilities

- Load captures
- Replay timing
- Recreate protocol activity

Publishes:

- ReplayStarted
- ReplayFinished

Consumes:

- Capture packages

---

# 9. Study Browser

## Responsibilities

- Navigate Patient/Study/Series/Instance hierarchy
- Search
- Filter
- Lazy loading

Publishes:

- StudySelected
- SeriesSelected
- InstanceSelected

---

# 10. DICOM Viewer

## Responsibilities

- Render images
- Window/Level
- Zoom
- Pan
- Cine playback
- Overlay

Publishes:

- ImageDisplayed

Consumes:

- InstanceSelected

Not responsible for diagnostic interpretation.

---

# 11. Metadata Inspector

## Responsibilities

- Browse tags
- Search tags
- Export metadata
- Compare metadata

Consumes:

- InstanceSelected

Publishes:

- MetadataViewed

---

# 12. Transfer Analysis

## Responsibilities

- Throughput
- Latency
- Compression
- Transfer syntax
- Recommendations

Publishes:

- AnalysisCompleted

Consumes:

- Association events
- Transfer events

---

# 13. Event Timeline

## Responsibilities

Present chronological engineering events for the selected object.

Consumes all timestamped events.

---

# 14. Logging

## Responsibilities

- Structured logging
- JSON logs
- Human-readable console logs

Consumes every event.

---

# 15. Reporting

## Responsibilities

Generate:

- HTML
- Markdown
- JSON
- CSV

Consumes:

- Captures
- Analysis
- Logs

Publishes:

- ReportGenerated

---

# 16. Plugin Host

## Responsibilities

- Discover plugins
- Load plugins
- Register extension points
- Dispatch hooks

Plugins may contribute:

- Diagnostics
- Reports
- Rules
- Vendor analyzers
- Commands

---

# 17. Settings

## Responsibilities

Manage:

- Configuration
- Profiles
- Preferences
- Paths
- Security options

Should never contain business logic.

---

# 18. REST API

## Responsibilities

Expose application capabilities.

Requirements:

- Stable contracts
- Versioning
- Authentication hooks
- OpenAPI documentation

The API should remain independent of UI implementation.

---

# 19. Storage

## Responsibilities

Persist:

- Configuration
- Events
- Captures
- Reports
- Logs
- Application state

The storage module abstracts persistence technology from higher layers.

---

# 20. Module Communication

Preferred communication:

Producer

↓

Event Bus

↓

Subscribers

Avoid tightly coupled module-to-module calls unless synchronous interaction is explicitly required.

---

# 21. Dependency Rules

Modules may depend on:

- Shared contracts
- Public APIs
- Event definitions

Modules must not depend on:

- Internal implementation of another module
- UI-specific code
- Plugin internals

---

# 22. Ownership Matrix

| Module | Owns |
|---------|------|
| Capture Engine | Capture lifecycle |
| Replay Engine | Replay lifecycle |
| Viewer | Image rendering |
| Metadata Inspector | Dataset inspection |
| Transfer Analysis | Performance analysis |
| Reporting | Report generation |
| Plugin Host | Extensions |
| Storage | Persistence |

Ownership should remain singular to avoid overlapping responsibilities.

---

# 23. Future Modules

Potential additions:

- DICOMweb
- HL7
- FHIR
- Remote Collector
- Fleet Management
- Distributed Capture
- Rule Engine
- Notification Service

These should integrate without redesigning existing modules.

---

# 24. Summary

The module boundaries defined here are considered architectural contracts.

Implementation teams and AI coding agents should work within these boundaries to maximize parallel development, minimize coupling, and preserve long-term maintainability.
