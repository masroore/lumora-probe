# 08-rest-api-specification.md

> **Project:** Lumora Probe
>
> **Document:** REST API Specification
>
> **Status:** Architecture Baseline
>
> **Audience:** Architects, Engineers, QA, Plugin Developers, Claude Code, Codex

---

# 1. Purpose

This document defines the high-level REST API architecture for Lumora Probe.

It establishes resource boundaries, API conventions, authentication expectations, versioning, and response patterns without prescribing implementation details.

---

# 2. Design Goals

The API SHALL be:

- Resource-oriented
- Versioned
- Consistent
- Self-documenting
- Secure
- Backward compatible
- Suitable for automation

The API is the canonical interface consumed by the Web UI, CLI, plugins, and external integrations.

---

# 3. API Principles

- Use HTTPS exclusively.
- JSON is the default representation.
- Resources use plural nouns.
- HTTP methods express intent.
- APIs should be idempotent where appropriate.
- Long-running operations should be asynchronous.

---

# 4. Versioning

Initial version:

```
/api/v1/
```

Breaking changes require a new major version.

---

# 5. Authentication

Implementation should support:

- API Keys
- OAuth2/OIDC (future)
- Local authentication
- Service accounts

Authentication strategy remains implementation-specific.

---

# 6. Resource Catalog

Core resources include:

- /system
- /associations
- /studies
- /series
- /instances
- /captures
- /replays
- /analysis
- /reports
- /plugins
- /settings
- /events
- /logs

---

# 7. Standard Operations

Resources should support, where applicable:

- List
- Retrieve
- Create
- Update
- Delete
- Search
- Export

Not every resource requires every operation.

---

# 8. Request & Response Conventions

Requests should use:

- JSON
- UTF-8
- ISO-8601 timestamps
- UUIDv7 identifiers where applicable

Responses should include:

- Data
- Metadata
- Pagination (when required)
- Links (optional)
- Error details (if applicable)

---

# 9. Error Model

Errors should provide:

- HTTP status
- Machine-readable error code
- Human-readable message
- Correlation ID
- Optional remediation guidance

---

# 10. Pagination

Collection endpoints should support:

- page
- page_size
- sort
- filter
- cursor (future)

---

# 11. Filtering & Search

Common capabilities:

- Full-text search
- Date filtering
- Status filtering
- Aggregate filtering
- Event filtering

---

# 12. Long-Running Operations

Operations such as replay, report generation, and large imports should:

- Return immediately
- Provide operation identifiers
- Expose progress endpoints

---

# 13. Event Integration

REST operations may publish domain events.

See:

- 06-event-driven-architecture.md

---

# 14. Security

The API should support:

- Authentication
- Authorization
- Audit logging
- Rate limiting
- Input validation
- PHI protection

---

# 15. Performance Guidance

The API should support:

- Compression
- Streaming
- Conditional requests
- Efficient pagination
- Large dataset handling

---

# 16. OpenAPI

The implementation should publish an OpenAPI specification generated from the service implementation.

Documentation should remain synchronized with code.

---

# 17. Extensibility

Future capabilities may include:

- DICOMweb
- FHIR
- HL7
- Webhooks
- Bulk operations

---

# 18. Acceptance Criteria

The API architecture is complete when:

- Resource boundaries are defined.
- Versioning strategy is documented.
- Authentication approach is established.
- Error model is consistent.
- Long-running operations are addressed.
- Security expectations are documented.
- Extension points are identified.

---

# 19. References

- 03-system-architecture.md
- 04-technology-stack.md
- 05-system-modules.md
- 06-event-driven-architecture.md
- 07-data-model.md
