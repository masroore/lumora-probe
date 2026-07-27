# 11-storage-architecture.md

> **Project:** Lumora Probe
>
> **Document:** Storage Architecture
>
> **Status:** Architecture Baseline
>
> **Audience:** Architects, Engineers, QA, Plugin Developers, Claude Code, Codex

---

# 1. Purpose

This document defines the high-level storage architecture for Lumora Probe.

It establishes storage principles, data classification, persistence responsibilities, and lifecycle management while leaving implementation details to subsequent design documents.

---

# 2. Objectives

The storage architecture SHALL:

- Preserve engineering evidence
- Support replayability
- Separate concerns
- Scale with large datasets
- Remain storage-engine independent
- Enable backup and recovery
- Support future storage providers

---

# 3. Storage Principles

- Domain-first
- Storage-independent
- Immutable evidence
- Explicit ownership
- Recoverable
- Versioned
- Observable

---

# 4. Data Classification

Primary data categories include:

- Configuration
- Metadata
- Domain entities
- Event streams
- Capture artifacts
- Replay artifacts
- Reports
- Logs
- Temporary data
- Cache

Each category may have different retention and performance requirements.

---

# 5. Storage Components

Typical storage components include:

- Metadata database
- Event store
- File repository
- Capture repository
- Replay repository
- Report repository
- Cache
- Configuration store

---

# 6. Metadata Storage

Metadata storage should contain:

- Domain entities
- Relationships
- Configuration
- Operational state

Physical schema is intentionally unspecified.

---

# 7. Event Storage

Event storage should:

- Preserve immutable events
- Support replay
- Maintain ordering guarantees where applicable
- Support efficient querying

Refer to:

- 06-event-driven-architecture.md

---

# 8. File Storage

Binary artifacts may include:

- DICOM files
- Capture archives
- Reports
- Logs
- Export packages

Implementations should abstract the underlying storage provider.

---

# 9. Caching

Caching may be used for:

- Frequently accessed metadata
- Viewer state
- Search results
- Generated reports

Cached data should always be recoverable.

---

# 10. Retention

Retention policies should define:

- Temporary data lifetime
- Log retention
- Capture retention
- Report retention
- Archive policies

Policies should be configurable.

---

# 11. Backup & Recovery

The platform should support:

- Scheduled backups
- Point-in-time recovery where practical
- Export/import
- Integrity verification
- Disaster recovery planning

---

# 12. Performance Guidance

Storage should support:

- Large studies
- Large capture sessions
- Streaming access
- Incremental loading
- Efficient indexing

Performance optimizations should not compromise integrity.

---

# 13. Security

Storage should support:

- Encryption at rest
- PHI protection
- Access control
- Audit logging
- Secure deletion where required

---

# 14. Extensibility

Future storage providers may include:

- PostgreSQL
- SQLite
- Object storage
- Cloud storage
- Distributed storage

Storage providers should implement common abstractions.

---

# 15. Monitoring

Expose metrics including:

- Capacity
- Growth
- Read/write latency
- Cache efficiency
- Storage errors
- Backup status

---

# 16. Acceptance Criteria

The storage architecture is complete when:

- Data categories are defined.
- Storage responsibilities are documented.
- Retention guidance exists.
- Backup expectations are established.
- Security expectations are documented.
- Extensibility points are identified.

---

# 17. References

- 03-system-architecture.md
- 04-technology-stack.md
- 05-system-modules.md
- 06-event-driven-architecture.md
- 07-data-model.md
- 10-plugin-sdk.md
