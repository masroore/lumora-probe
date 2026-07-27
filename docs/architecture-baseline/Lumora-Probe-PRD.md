# Lumora Probe — Product Requirements Document (PRD)

> **Version:** 0.9 (Architecture Baseline)
>
> **Status:** Draft
>
> **Audience:** Product Management, Architecture, Claude Code, Codex, Engineering

---

# 1. Executive Summary

Lumora Probe is a **DICOM observability and troubleshooting platform** designed for PACS administrators, healthcare integration engineers, medical imaging vendors, field service engineers, and software developers.

The product focuses on **understanding, capturing, replaying, analyzing, and troubleshooting DICOM communications** rather than providing diagnostic image interpretation.

It combines:

- DICOM networking tools
- Capture and replay
- Transfer analytics
- Event-driven observability
- Lightweight DICOM image viewer
- Metadata inspector
- Structured logging
- Reporting
- Vendor-specific diagnostics

This document defines the product vision, scope, architecture, functional requirements, non-functional requirements, and implementation constraints.

---

# 2. Vision

## Mission

Build the best engineering tool for understanding DICOM networking.

Think:

- Wireshark
- Chrome DevTools
- Seq
- Grafana

combined for DICOM.

---

# 3. Target Users

- PACS administrators
- Healthcare integration engineers
- Vendor support engineers
- Medical imaging software developers
- QA engineers
- Technical consultants

Not intended for primary diagnostic interpretation.

---

# 4. Product Principles

- Headless-first
- Event-driven
- Modular
- Keyboard-centric
- Server-rendered UI
- Fast startup
- Minimal dependencies
- Cross-platform
- Plugin-based
- Observability-first

---

# 5. Non Goals

The application will NOT become:

- Diagnostic workstation
- RIS
- PACS archive
- Reporting workstation
- 3D workstation
- MPR viewer
- AI workstation

---

# 6. Core Modules

- CLI
- REST API
- Web UI
- Capture Engine
- Replay Engine
- Study Browser
- DICOM Viewer
- Metadata Inspector
- Event System
- Plugin System
- Reporting
- Settings

---

# 7. Technology Stack

## Backend

- Python 3.13+
- uv
- FastAPI
- Uvicorn
- Pydantic v2
- pydantic-settings
- pynetdicom
- pydicom
- SQLAlchemy Core
- SQLite
- DuckDB
- structlog
- orjson
- pluggy
- Jinja2

## Frontend

- Tailwind CSS 4
- HTMX
- Alpine.js
- Chart.js
- Cornerstone3D
- Tabulator
- Lucide Icons
- Vanilla JavaScript

---

# 8. High-Level Architecture

- Headless core
- REST API
- WebSocket event stream
- Event bus
- Storage layer
- Plugin layer
- CLI frontend
- Browser frontend

All UI components consume the same backend services.

---

# 9. Event-Driven Architecture

Everything emits typed events.

Examples:

- AssociationStarted
- AssociationReleased
- CStoreReceived
- ImageDecoded
- ImageDisplayed
- DatasetParsed
- WarningRaised
- ErrorRaised

Subscribers:

- Logger
- SQLite
- Web UI
- CLI
- Metrics
- Plugins
- Reports

---

# 10. Functional Requirements

## Dashboard

Display:

- Active associations
- Images received
- MB/sec
- Images/sec
- Warnings
- Errors
- Recent captures

---

## Live Monitor

- Live associations
- Live transfers
- Live throughput
- Live events
- WebSocket updates

---

## Study Browser

Hierarchy

Patient

→ Study

→ Series

→ Instances

Features

- Lazy loading
- Search
- Filter
- Collapse/expand
- Badges
- Bookmarks

---

# 11. Simple DICOM Viewer

Purpose:

Engineering inspection.

Not diagnosis.

## Layout

Left

- Study navigator

Center

- Image canvas

Right

Tabbed inspector

- Properties
- Metadata
- Transfer
- Analysis
- Events

Bottom (collapsible)

- Logs
- DIMSE
- Raw Dataset
- Hex

## Viewer Features

- Window/Level
- Zoom
- Pan
- Fit
- 1:1
- Invert
- Reset
- Multi-frame slider
- Cine playback
- Fullscreen
- Overlay toggle

Keyboard:

- Left/Right: previous/next instance
- Up/Down: previous/next instance
- PageUp/PageDown: jump 10
- Home/End
- + / -
- F (fit)
- 0 (reset)
- I (invert)
- M (metadata)

---

# 12. Metadata Inspector

- Search
- Copy tag
- Copy value
- JSON export
- Raw DICOM dump
- Hide/show private tags

---

# 13. Transfer Inspector

Display

- Association ID
- Presentation Context
- Transfer Syntax
- Receive duration
- Decode duration
- File size
- Compression
- PDU size

---

# 14. Event Timeline

Per instance:

Associate

↓

Receive

↓

Decode

↓

Persist

↓

Display

↓

Release

---

# 15. Capture Engine

Capture

- Associations
- DIMSE
- Metadata
- Images
- Logs

Persist as portable capture.

---

# 16. Replay Engine

Replay

- Associations
- Timing
- Messages
- Images

Purpose:

Reproduce production issues.

---

# 17. Reporting

Generate

- HTML
- Markdown
- JSON
- CSV

---

# 18. REST API

Representative endpoints

GET /studies

GET /series

GET /instances

GET /metadata

GET /events

GET /logs

GET /analysis

GET /captures

---

# 19. Plugin System

Use pluggy.

Plugins may provide

- Vendor analyzers
- Reports
- Rules
- Diagnostics
- Decoders

---

# 20. Logging

Every event is structured.

Outputs

- stdout
- app.log
- events.jsonl
- SQLite

---

# 21. Security

- Local-first
- No outbound telemetry
- Read-only viewer
- Optional authentication
- Audit logging

---

# 22. Performance

Goals

- UI responsive <100 ms
- Lazy image loading
- Only current ±2 images decoded
- Virtualized tables
- Large studies supported

---

# 23. Testing

- Unit
- Integration
- Replay regression
- DICOM conformance
- Performance
- UI

---

# 24. Roadmap

Phase 1

Foundation

Phase 2

Networking

Phase 3

Capture

Phase 4

Viewer

Phase 5

Replay

Phase 6

Reporting

Phase 7

Plugins

Phase 8

Advanced analytics

---

# 25. Future Enhancements

- Fleet monitoring
- Multi-node collectors
- Remote agents
- Vendor dashboards
- DICOMweb support
- HL7/FHIR integrations

---

# 26. Acceptance Criteria

The product shall:

- Capture DICOM associations
- Persist events
- Display studies
- Render images
- Inspect metadata
- Replay captures
- Produce reports
- Support plugins
- Expose REST API
- Stream live events

---

# Appendix

## Repository Structure

```text
docs/
src/
tests/
plugins/
captures/
reports/
config/
docker/
```

## Design Philosophy

The image viewer exists to support engineering investigations.

The primary value of Lumora Probe is correlating:

- image
- metadata
- DICOM protocol
- transfer timing
- logs
- events
- diagnostics

into a unified troubleshooting workflow.

---

# Note to Implementation Models

This PRD intentionally specifies product behavior and architecture rather than implementation details.

Claude Code or Codex should derive:

- ADRs
- Work Breakdown Structure
- Technical design
- Database schema
- API contracts
- Package layout
- Milestones
- Implementation plan

while preserving the architectural principles and constraints defined in this document.
