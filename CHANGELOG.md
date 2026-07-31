# Changelog

All notable releases use Semantic Versioning. Release `0.x` indicates an engineering
platform whose public contracts may still evolve before `1.0.0`; documented ADRs and API
artifacts govern compatibility changes.

## [0.1.0] — 2026-07-31

### Added

- DICOM association capture, event persistence, rolling evidence, and `.lpcap` packages.
- Replay, analysis, reports, redaction, bookmarks, and handover workflows.
- Study browser, metadata and transfer inspectors, image viewer, live timeline, and WebSocket
  event streaming.
- REST API with generated OpenAPI, health/readiness endpoints, and read-only mode.
- Trusted in-process plugin SDK and bundled plugin management.
- Metrics, audit logging, security/path validation, accessibility themes, and keyboard workflows.
- Wheel/sdist packaging with committed offline assets, no-Node installation, and non-root Docker
  distribution.
- Scheduled interoperability suites against DCMTK, dcm4che, and Orthanc, including the release
  transfer-syntax matrix.
- Probe Lite receiver and Sender Lite one-shot sender with cross-platform module and console
  entry points, deterministic Lite logging, and trusted-network exit-code contracts.

### Verification

- Python quality gates: formatting, lint, import boundaries, static analysis, and full tests.
- Full default suite: `496 passed, 17 skipped`.
- Scheduled interoperability suite: `14 passed, 0 failed`.
- Committed asset drift check: pass.
- PRD acceptance and Definition-of-Done audits: pass with documented evidence.

### Limitations

See [`docs/guides/known-limitations.md`](docs/guides/known-limitations.md). In particular,
C-MOVE object sub-operations, built-in authentication/RBAC, PS3.15 conformance, and plugin
sandboxing are not release capabilities.
