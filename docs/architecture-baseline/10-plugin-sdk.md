# 10-plugin-sdk.md

> **Project:** Lumora Probe
>
> **Document:** Plugin SDK Architecture
>
> **Status:** Architecture Baseline
>
> **Audience:** Architects, Engineers, QA, Plugin Developers, Claude Code, Codex

---

# 1. Purpose

This document defines the architectural principles for the Lumora Probe Plugin SDK.

It establishes how extensions integrate with the application while preserving stability, security, and compatibility. Detailed APIs and implementation are intentionally deferred.

---

# 2. Objectives

The Plugin SDK SHALL:

- Enable first- and third-party extensions
- Decouple optional functionality
- Preserve core stability
- Support event-driven integration
- Allow independent evolution
- Maintain backward compatibility

---

# 3. Design Principles

- API-first
- Event-driven
- Capability-based
- Secure by default
- Versioned
- Discoverable
- Extensible

---

# 4. Plugin Lifecycle

Typical lifecycle:

```
Discover
↓
Validate
↓
Load
↓
Initialize
↓
Start
↓
Stop
↓
Unload
```

Plugins should fail independently without affecting the core application.

---

# 5. Plugin Types

Typical plugin categories include:

- Importers
- Exporters
- Analysis engines
- Report generators
- Viewers
- Event processors
- Storage providers
- Authentication providers
- Notification providers

---

# 6. Manifest

Each plugin should declare:

- Identifier
- Name
- Version
- Author
- Description
- Capabilities
- Dependencies
- Compatibility
- Configuration schema

---

# 7. Discovery

The platform should support:

- Local plugins
- Bundled plugins
- Development plugins
- Future package repositories

Discovery mechanisms remain implementation-specific.

---

# 8. Extension Points

Plugins may extend:

- Event processing
- REST API
- WebSocket streams
- Reports
- Analysis pipelines
- Viewer tools
- Settings UI
- Background jobs

Core behavior should remain stable.

---

# 9. Event Integration

Plugins may:

- Publish events
- Subscribe to events
- Enrich event data

All event interactions shall comply with:

- 06-event-driven-architecture.md

---

# 10. Dependency Injection

Plugins should receive required services through dependency injection rather than constructing core services directly.

---

# 11. Configuration

Plugins may define:

- Configuration schema
- Default values
- Validation rules
- Runtime settings

Configuration storage is implementation-specific.

---

# 12. Versioning

The SDK should define:

- SDK version
- Compatibility policy
- Deprecation process
- Migration guidance

Breaking SDK changes require a new major version.

---

# 13. Security

The platform should support:

- Capability restrictions
- Permission checks
- Secure configuration
- Audit logging
- PHI protection

Plugins should follow the principle of least privilege.

---

# 14. Packaging

Packaging guidance should define:

- Directory structure
- Assets
- Metadata
- Distribution format
- Installation workflow

---

# 15. Testing

Plugin authors should provide:

- Unit tests
- Integration tests
- Compatibility tests
- Configuration validation

---

# 16. Documentation

Every plugin should include:

- Overview
- Installation
- Configuration
- Compatibility
- Changelog
- Troubleshooting

---

# 17. Acceptance Criteria

The SDK architecture is complete when:

- Lifecycle is documented.
- Discovery strategy is defined.
- Extension points are identified.
- Versioning policy is documented.
- Security expectations are established.
- Plugin packaging guidance is available.

---

# 18. References

- 03-system-architecture.md
- 04-technology-stack.md
- 05-system-modules.md
- 06-event-driven-architecture.md
- 07-data-model.md
- 08-rest-api-specification.md
- 09-websocket-specification.md
