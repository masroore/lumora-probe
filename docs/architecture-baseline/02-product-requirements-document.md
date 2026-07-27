# 02-product-requirements-document.md

> **Project:** Lumora Probe
>
> **Document:** Product Requirements Document (PRD)
>
> **Status:** Baseline v1.0
>
> **Audience:** Product Management, Architecture, Engineering, QA, Claude Code, Codex

---

# 1. Introduction

## 1.1 Purpose

This Product Requirements Document (PRD) defines the functional and non-functional requirements for Lumora Probe.

It is the authoritative specification describing **what** the product shall do. It intentionally avoids implementation details, algorithms, package structure, and source code organization, which belong in the technical architecture and implementation plans.

## 1.2 Scope

Lumora Probe is an engineering application for observing, capturing, replaying, analyzing, and troubleshooting DICOM communication.

The application provides a unified workspace for protocol inspection, metadata exploration, lightweight image viewing, event correlation, structured logging, and diagnostics.

## 1.3 Goals

The product shall enable engineers to:

- Observe live DICOM traffic
- Investigate interoperability issues
- Diagnose transfer failures
- Analyze performance bottlenecks
- Inspect DICOM metadata
- Replay captured sessions
- Generate investigation reports
- Extend functionality through plugins

## 1.4 Non-Goals

This product shall not become:

- Diagnostic workstation
- PACS archive
- RIS
- EMR
- Clinical reporting system
- AI diagnosis platform
- Enterprise VNA

---

# 2. Product Overview

Lumora Probe combines several engineering capabilities into a single application:

- Live DICOM monitoring
- Association inspection
- DIMSE inspection
- Metadata browser
- Lightweight DICOM viewer
- Event timeline
- Capture and replay
- Transfer analytics
- Reporting
- Structured logging

The objective is to reduce the time required to determine the root cause of DICOM interoperability problems.

---

# 3. Personas

## PACS Administrator

Needs to investigate production failures rapidly.

### Primary Tasks

- Review failed transfers
- Inspect associations
- Validate studies
- Generate reports

---

## Integration Engineer

Needs visibility into DICOM protocol exchanges.

### Primary Tasks

- Debug C-STORE
- Analyze presentation contexts
- Verify transfer syntaxes
- Measure throughput

---

## Vendor Support Engineer

Needs reproducible customer evidence.

### Primary Tasks

- Capture sessions
- Replay failures
- Compare behavior
- Produce diagnostic bundles

---

## Software Developer

Needs deterministic debugging.

### Primary Tasks

- Test implementations
- Compare protocol behavior
- Inspect datasets
- Analyze timing

---

# 4. User Stories

## Live Monitoring

As a PACS administrator,

I want to see active associations,

so that I can immediately identify communication issues.

---

As an integration engineer,

I want every protocol event timestamped,

so I can reconstruct exactly what happened.

---

As a developer,

I want replayable captures,

so I can reproduce production failures locally.

---

As a support engineer,

I want to inspect metadata without opening another application,

so that troubleshooting remains in one workspace.

---

# 5. Core Functional Areas

The product consists of the following primary modules:

1. Dashboard
2. Live Monitor
3. Study Browser
4. DICOM Viewer
5. Metadata Inspector
6. Transfer Analysis
7. Event Timeline
8. Logs
9. Capture Manager
10. Replay Manager
11. Reports
12. Settings
13. Plugin Manager

Each module will be specified independently in subsequent sections.

---

# 6. Product Requirements

Each requirement throughout this PRD will be categorized using the following priorities.

| Priority | Meaning |
|-----------|---------|
| Must | Required for initial release |
| Should | Strongly recommended |
| Could | Nice to have |
| Future | Out of scope for current release |

---

# 7. Functional Themes

The product is organized around six engineering workflows.

## Observe

Monitor live protocol activity.

## Capture

Persist engineering evidence.

## Inspect

Browse images, metadata and events.

## Analyze

Detect anomalies automatically.

## Replay

Reproduce captured behavior.

## Report

Generate portable investigation artifacts.

---

# 8. High-Level Navigation

The application shall provide access to:

- Dashboard
- Live Monitor
- Studies
- Captures
- Replay
- Reports
- Plugins
- Settings

Navigation shall remain consistent throughout the application.

---

# 9. UX Principles

The interface shall prioritize:

- keyboard efficiency
- low latency
- progressive disclosure
- information density
- responsive layouts
- accessibility

Every major screen shall support search where practical.

---

# 10. Acceptance Criteria

The PRD is considered complete when all remaining sections define:

- detailed functional requirements
- UI behavior
- workflows
- permissions
- validation rules
- error handling
- acceptance criteria
- future considerations

The following documents will expand upon this PRD:

- 03-system-architecture.md
- 04-technology-stack.md
- 05-ui-ux-guidelines.md
- Module specifications for each major feature

---

## Document Roadmap

Subsequent revisions of this PRD will include dedicated chapters for:

1. Dashboard
2. Live Monitor
3. Study Browser
4. DICOM Viewer
5. Metadata Inspector
6. Transfer Analysis
7. Event Timeline
8. Logs
9. Capture Engine
10. Replay Engine
11. Reporting
12. Plugin Framework
13. Security
14. Performance
15. Accessibility
16. Error Handling
17. Non-Functional Requirements
18. Release Acceptance Criteria

> This document intentionally serves as the master functional specification. Implementation details belong in the Architecture, ADR, and Technical Design documents.
