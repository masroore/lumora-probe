# 00-project-charter.md

> **Project:** Lumora Probe  
> **Document:** Project Charter  
> **Status:** Approved Baseline  
> **Audience:** Product, Architecture, Engineering, Claude Code, Codex

---

# 1. Purpose

This document is the constitutional document for the Lumora Probe project.

Every architectural decision, implementation plan, ADR, feature proposal, and pull request **must comply with this charter** unless it is formally amended.

When there is a conflict between this document and later implementation notes, this document takes precedence.

---

# 2. Mission

Lumora Probe is an engineering platform for **observing, capturing, replaying, analyzing, and troubleshooting DICOM communications**.

Its goal is to make diagnosing DICOM networking problems as productive as debugging modern web applications with browser developer tools.

The product prioritizes observability, traceability, reproducibility, and engineering workflows over clinical interpretation.

---

# 3. Product Vision

Lumora Probe should become the first tool engineers reach for when they need to answer questions such as:

- Why did this C-STORE fail?
- Which transfer syntax was negotiated?
- Why is this modality slow?
- Which DIMSE messages were exchanged?
- Can I replay this production issue?
- What happened during this association?
- Why won't this scanner communicate with the PACS?

---

# 4. Target Users

Primary users:

- PACS Administrators
- Integration Engineers
- Medical Imaging Software Developers
- Vendor Support Engineers
- Field Service Engineers
- QA Engineers
- Healthcare IT Consultants

Secondary users:

- Technical Trainers
- Product Managers
- Support Teams

---

# 5. Product Scope

Lumora Probe provides:

- DICOM networking
- Live monitoring
- Event timeline
- Capture & replay
- Metadata inspection
- Lightweight DICOM viewing
- Transfer analysis
- Structured logging
- Reporting
- Plugin framework
- REST API
- CLI

---

# 6. Explicit Non-Goals

The project will NOT become:

- Diagnostic workstation
- PACS archive
- RIS
- EMR
- Image reporting system
- 3D workstation
- MPR viewer
- AI diagnostic platform
- Clinical measurement application

Clinical workflows are intentionally outside project scope.

---

# 7. Product Philosophy

The image is **one piece of evidence**, not the product.

The primary workflow is investigation:

Image
→ Metadata
→ Network
→ Events
→ Logs
→ Analysis
→ Root Cause

Every feature should support this workflow.

---

# 8. Architectural Principles

1. Headless-first
2. Event-driven
3. Modular
4. API-first
5. Plugin-oriented
6. Local-first
7. Cross-platform
8. Testable
9. Observable
10. Maintainable

---

# 9. Technology Direction

Backend:

- Python 3.13+
- FastAPI
- Pydantic v2
- pynetdicom
- pydicom
- SQLAlchemy Core
- SQLite
- pluggy

Frontend:

- HTMX
- Alpine.js
- Tailwind CSS 4
- Chart.js
- Cornerstone3D
- Tabulator

Major technology changes require an ADR.

---

# 10. User Experience Principles

The application should feel like:

- Visual Studio Code
- Chrome DevTools
- Wireshark

It should **not** resemble a traditional radiology workstation.

The interface should be:

- keyboard friendly
- responsive
- information dense
- uncluttered
- engineer focused

---

# 11. Definition of Done

A feature is complete only when:

- Functional implementation is finished.
- Automated tests exist.
- Documentation is updated.
- APIs are documented.
- Logging is implemented.
- Error handling is complete.
- Accessibility is considered.
- Performance expectations are met.

---

# 12. Documentation Hierarchy

1. Project Charter
2. PRD
3. ADRs
4. Architecture
5. Technical Design
6. WBS
7. Implementation Tasks

Higher-level documents always take precedence.

---

# 13. AI Development Workflow

AI coding agents should:

1. Read this Project Charter.
2. Read the PRD.
3. Read applicable ADRs.
4. Produce or review the implementation plan.
5. Implement **one phase only**.
6. Update documentation.
7. Update the WBS.
8. Never redesign approved architecture without justification and an ADR.

---

# 14. Success Criteria

Lumora Probe succeeds if users can:

- Diagnose DICOM networking problems quickly.
- Reproduce production failures.
- Inspect any transferred object.
- Correlate events, metadata, logs, and images.
- Extend the platform through plugins.

---

# 15. Guiding Statement

> "Lumora Probe is an observability platform for DICOM ecosystems. Every feature should improve an engineer's ability to understand, diagnose, and reproduce system behavior."

