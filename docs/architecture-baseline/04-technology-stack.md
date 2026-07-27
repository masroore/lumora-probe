# 04-technology-stack.md

> **Project:** Lumora Probe
>
> **Document:** Technology Stack
>
> **Status:** Approved Baseline
>
> **Audience:** Architects, Engineers, Claude Code, Codex

---

# 1. Purpose

This document defines the approved technology stack for Lumora Probe.

Its objectives are to:

- Freeze major technology decisions.
- Explain why each technology was selected.
- Prevent unnecessary architectural churn.
- Provide guidance for future contributors and AI coding agents.

Unless superseded by an ADR, the technologies in this document are considered the project's approved baseline.

---

# 2. Technology Selection Principles

Every technology should satisfy most of the following:

- Mature and production proven
- Active community and maintenance
- Excellent documentation
- Cross-platform support
- Minimal operational complexity
- Strong type safety where practical
- Easy local development
- Good performance
- Long-term maintainability

---

# 3. Approved Stack Overview

| Area | Technology |
|------|------------|
| Language | Python 3.13+ |
| Package Manager | uv |
| Build Backend | Hatchling |
| Web Framework | FastAPI |
| ASGI Server | Uvicorn |
| Validation | Pydantic v2 |
| Configuration | pydantic-settings |
| DICOM Networking | pynetdicom |
| DICOM Parsing | pydicom |
| Image Rendering | Cornerstone3D |
| Frontend | HTMX + Alpine.js |
| Styling | Tailwind CSS 4 |
| Data Tables | Tabulator |
| Charts | Chart.js |
| Logging | structlog + logging |
| Database | SQLite |
| Query Layer | SQLAlchemy Core |
| Analytics | DuckDB |
| Serialization | orjson |
| Plugin System | pluggy |
| Templates | Jinja2 |
| Testing | pytest |
| Linting | Ruff |
| Static Analysis | BasedPyright |

---

# 4. Backend

## Python 3.13+

### Why

- Modern language features
- Excellent ecosystem
- Strong DICOM libraries
- Excellent typing support

### Alternatives Considered

- Go
- Rust
- C#
- Java

Python offers the best balance between ecosystem maturity and developer productivity for this project.

---

## FastAPI

Responsibilities:

- REST API
- Dependency injection
- OpenAPI generation
- WebSocket endpoints

Chosen because of:

- Excellent async support
- Strong typing
- Pydantic integration
- High developer productivity

---

## Uvicorn

Chosen because:

- Lightweight
- Fast
- Native FastAPI integration

---

## Pydantic v2

Used for:

- Request validation
- Response models
- Configuration
- Domain validation

---

## pydantic-settings

Centralized configuration management.

Configuration precedence:

1. Environment variables
2. .env files
3. TOML/YAML configuration
4. Defaults

---

# 5. DICOM Stack

## pynetdicom

Responsibilities:

- Association management
- DIMSE messaging
- SCP/SCU roles
- Negotiation

---

## pydicom

Responsibilities:

- Dataset parsing
- Metadata
- Pixel data
- File IO

---

## Image Codecs

Primary:

- pylibjpeg
- pylibjpeg-openjpeg

Optional:

- GDCM

---

# 6. Data Storage

## SQLite

Primary operational database.

Reasons:

- Zero administration
- Portable
- Reliable
- Embedded
- Excellent tooling

Not intended as a long-term PACS archive.

---

## SQLAlchemy Core

Use SQLAlchemy Core only.

Do not use the ORM.

Reasons:

- Explicit SQL
- Better control
- Simpler debugging
- Easier optimization

---

## DuckDB

Purpose:

- Analytics
- Large log exploration
- Report generation

Not used for operational state.

---

# 7. Frontend

## HTMX

Primary interaction model.

Reasons:

- Server-rendered UI
- Minimal JavaScript
- Excellent productivity
- Progressive enhancement

---

## Alpine.js

Responsibilities:

- Local component state
- Small interactive behaviors

Avoid large client-side application logic.

---

## Tailwind CSS 4

Used for:

- Layout
- Responsive design
- Utility styling

Custom CSS should remain minimal.

---

## Cornerstone3D

Purpose:

Lightweight engineering image viewer.

Not intended to implement diagnostic workstation features.

---

## Tabulator

Used for:

- Large tables
- Virtual scrolling
- Sorting
- Filtering

---

## Chart.js

Provides:

- Throughput charts
- Latency
- Trend visualization
- Performance metrics

Complex scientific visualization is intentionally out of scope.

---

# 8. Logging

## structlog

Primary structured logging layer.

Requirements:

- JSON support
- Human-readable console
- Context enrichment

---

## Python logging

Underlying logging implementation.

---

# 9. Serialization

## orjson

Used wherever high-performance JSON serialization is required.

---

# 10. Plugin Framework

## pluggy

Responsibilities:

- Extension points
- Vendor integrations
- Custom analyzers
- Report generators

Plugins must rely only on documented extension APIs.

---

# 11. Templates

## Jinja2

Used for:

- HTML reports
- Markdown reports
- Email/report templates

---

# 12. Quality Tooling

## pytest

Testing framework.

## Ruff

Formatting, linting, import organization.

## BasedPyright

Static type analysis.

---

# 13. Technologies Intentionally Not Used

Unless approved by ADR, the following are excluded:

## Backend

- Django
- Flask
- Celery
- RabbitMQ
- Kafka
- Redis (core dependency)

## Frontend

- React
- Angular
- Vue
- Svelte

## Databases

- PostgreSQL (core runtime)
- MySQL
- MongoDB

These technologies may appear in future integrations but are not part of the baseline architecture.

---

# 14. Dependency Policy

- Prefer small dependencies.
- Avoid overlapping libraries.
- Remove unused packages.
- Pin versions.
- Review licenses.
- Minimize transitive dependencies.

---

# 15. AI Agent Guidance

AI coding agents shall:

- Use only approved technologies.
- Avoid introducing new frameworks without justification.
- Propose ADRs before major technology changes.
- Prefer consistency over novelty.

---

# 16. Summary

The approved technology stack reflects the project's priorities:

- Simplicity
- Maintainability
- Observability
- Developer productivity
- Engineering-focused workflows

Technology decisions should remain stable throughout the project lifecycle unless formally revised through the ADR process.
