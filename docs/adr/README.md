# Architecture Decision Records

Per ADR-0001, the architecture baseline in `../architecture-baseline/` is binding where it
is specific and silent elsewhere. This directory is the authoritative resolution layer for
everything it leaves open, and the only permitted route for deviating from something it
states specifically.

Baseline documents are cited by number (`06` §9 = `06-event-driven-architecture.md`
section 9). `00` is the Charter, `01` the Product Vision, `02` the PRD.

## Foundational

| ADR | Decision |
|-----|----------|
| [0001](ADR-0001-baseline-is-constitutional.md) | Baseline is constitutional, not a blueprint; gaps resolve by ADR |
| [0002](ADR-0002-concurrency-model.md) | Loop-owned event bus, one thread boundary at the DICOM edge |
| [0007](ADR-0007-runtime-topology.md) | Single process, transport-abstracted ingress, draining shutdown |
| [0012](ADR-0012-package-structure.md) | Module-first slices, boundaries enforced by import-linter in CI |
| [0011](ADR-0011-data-directory-layout.md) | One `LUMORA_DATA_DIR` root, OS-conventional default |
| [0017](ADR-0017-time-and-ordering.md) | `occurred_at` / `monotonic_ns` / `sequence`, each with one job |
| [0006](ADR-0006-domain-and-boundary-models.md) | Plain-Python domain, Pydantic at boundaries |

## Observation and capture

| ADR | Decision |
|-----|----------|
| [0003](ADR-0003-observation-topology.md) | Inline proxy on an endpoint foundation; association pairs are first-class |
| [0024](ADR-0024-service-agnostic-relay.md) | Service-agnostic relay, additive per-service enrichment |
| [0004](ADR-0004-capture-package-format.md) | Capture = directory; `.lpcap` interchange; DB is a rebuildable index |
| [0008](ADR-0008-always-on-ring-buffer.md) | Always-on bounded ring buffer plus promotable sessions |
| [0014](ADR-0014-event-granularity.md) | Domain events on the bus, PDU trace beside it |
| [0005](ADR-0005-replay-fidelity-tiers.md) | Event replay and protocol replay in v1; fidelity tiers gate both |
| [0013](ADR-0013-studies-are-projections.md) | Study/Series/Instance are projections over captures |
| [0018](ADR-0018-conditions-versus-findings.md) | Observed conditions vs inferred findings, physically separate |
| [0029](ADR-0029-cascade-semantics.md) | Capture deletion recomputes projections and preserves study-level references |

## Interfaces

| ADR | Decision |
|-----|----------|
| [0009](ADR-0009-no-authentication-in-v1.md) | No authentication in v1; TLS is a deployment concern |
| [0010](ADR-0010-network-exposure-gate.md) | Loopback default; non-loopback bind needs explicit acknowledgment |
| [0019](ADR-0019-dual-websocket-endpoints.md) | JSON stream for consumers, HTML fragments for the UI |
| [0015](ADR-0015-server-decode-client-render.md) | Server decodes pixels; Cornerstone3D renders only |
| [0016](ADR-0016-client-asserted-events.md) | Client-asserted events admitted, quarantined via mandatory `origin` |
| [0020](ADR-0020-configuration-tiers.md) | Immutable startup config vs live runtime settings, provenance shown |

## Platform

| ADR | Decision |
|-----|----------|
| [0021](ADR-0021-plugins-are-trusted-code.md) | Plugins are trusted in-process code; manifest is disclosure |
| [0023](ADR-0023-background-operations.md) | In-memory jobs, durable audit, never auto-resumed; `index.db` / `app.db` split |
| [0022](ADR-0022-test-strategy-weighting.md) | Component-weighted tests; injected `Clock` and `IdGenerator` |
| [0025](ADR-0025-frontend-asset-pipeline.md) | Node at asset-build time only; built assets committed |
| [0026](ADR-0026-redaction-and-handover.md) | Honest partial redaction; object-dropping is the default handover |
| [0030](ADR-0030-ratified-performance-budgets.md) | Ratified capture volume and rolling-retention budgets |
| [0031](ADR-0031-browser-e2e-test-tooling.md) | Playwright as dev-only browser e2e test tooling |
| [0033](ADR-0033-analysis-ownership-and-transfer-boundary.md) | Analysis ownership and Transfer Analysis boundary |
| [0034](ADR-0034-neutral-dicom-common-infrastructure.md) | Neutral DICOM mechanics shared without sharing product workflows |

## Probe Lite tools

| ADR | Decision |
|-----|----------|
| [0027](ADR-0027-sender-study-association-boundary.md) | Sender Lite uses one exact-fidelity association per Study |
| [0028](ADR-0028-lite-shared-common-library.md) | Shared `lumora_lite_common` for logger, signals, validators, UIDs |

## Recorded deviations from the baseline

Each is argued in full in its ADR.

- `08` §3 "HTTPS exclusively" — superseded; TLS is a reverse-proxy concern (0009).
- `12` §3 secure-by-default, DICOM plane only — associations are accepted by default,
  because an association Probe rejects is one it cannot show you (0009).
- `12` §7 role-based access control — no identities exist in v1; read-only is a
  server-wide mode behind a single enforcement seam (0009).
- `12` §15 secure defaults — the ring buffer ships enabled, a deliberate PHI tradeoff (0008).
- `04` §4 "domain validation" via Pydantic — read as boundary validation, not as
  aggregates inheriting `BaseModel` (0006).
- `03` §4 four-layer structure — preserved as lint rules inside module slices rather than
  as top-level directories (0012).
- `06` §9 "rely on `occurred_at` … instead of arrival order" — unsafe as written; ordering
  moves to a gap-free `sequence` (0017).
- `02` §20 four output sinks — rejected as 4× write amplification on the hot path (0014).
- `05` §10 Viewer publishes `ImageDisplayed` — retained but quarantined as
  client-asserted (0016).
- `13` §4 unit-heavy pyramid — weighted to component level, where this system's bugs
  actually live (0022).
- `10` §13 / `12` §11 enforced plugin capabilities — impossible in-process; the manifest is
  disclosure, and what *is* enforceable is built (0021).
- `07` §4 Study as a top-level aggregate — demoted to a projection, to avoid becoming the
  PACS archive Charter §6 forbids (0013).

## Deferred, each needing its own ADR before implementation

pcap import plugin (0003) · byte-exact / mock-peer replay (0005) · remote collectors
(0007) · multi-user auth and RBAC (0009) · plugin installation over the API (0021) ·
config profiles (0020) · DIMSE-N enrichment (0024) · Prometheus exposition as a plugin
(0014) · PS3.15 de-identification profile as a plugin (0026)
