# 06 — Deliverables

> **Project:** Lumora Probe
>
> **Document:** Deliverables
>
> **Status:** Planning Baseline
>
> **Audience:** Engineering, QA, Architects

---

# 1. Purpose

What each phase produces, as inspectable artifacts. A deliverable is something a reviewer
can open — code at a path, a generated file, a passing suite, a published document.

`01-work-breakdown-structure.md` §2.2 sets the default per task: implementation, tests at
the prescribed layer, docstrings, and any ADR-required documentation. This document lists
what is additional or phase-defining.

---

# 2. Deliverable classes

| Class | Meaning |
|-------|---------|
| **Code** | Source at a stated path |
| **Artifact** | Generated output, committed or published (catalog, OpenAPI, assets, packages) |
| **Suite** | A named test suite that must pass |
| **Document** | Written output under `docs/` |
| **Decision** | An accepted ADR |

---

# 3. Per-phase deliverables

## Phase 01 — Architecture Review

| Class | Deliverable |
|-------|-------------|
| Document | `docs/planning/00-architecture-review-findings.md` |
| Document | This planning set (01–08) |
| Decision | ADR-0027 — authoritative PRD |
| Decision | ADR-0030 — non-functional budgets (draft) |
| Document | Gap register, folded into the WBS traceability table |

## Phase 02 — Repository Foundation

| Class | Deliverable |
|-------|-------------|
| Code | `pyproject.toml` — uv + Hatchling, Python 3.13+ |
| Code | Nine slices under `src/lumora_probe/`, each with `domain/service/repository/api/contracts` |
| Artifact | `.importlinter` — six contracts |
| Suite | Boundary-violation suite proving each contract fails on a deliberate breach |
| Document | README, CONTRIBUTING (stating the ADR requirement for deviations), LICENCE |

## Phase 03 — Development Infrastructure

| Class | Deliverable |
|-------|-------------|
| Artifact | CI workflow with six gating checks |
| Code | `tests/conftest.py`, marker taxonomy (unit, component, dicom, e2e, interop, slow) |
| Code | `scripts/generate_fixtures.py` — synthetic DICOM, reviewable as code |
| Artifact | Generated fixture set; **no real patient data in the repository** |
| Document | pynetdicom threading spike report |
| Document | Provisional non-functional budgets |
| Code | Interop container definitions (scheduled, non-gating) |
| Code | Golden `.lpcap` comparison harness scaffold |

## Phase 04 — Core Infrastructure

| Class | Deliverable |
|-------|-------------|
| Code | `core/config.py` — startup tier, immutable |
| Code | `settings/` — runtime tier with provenance |
| Code | `core/paths.py` — data root, containment, network-FS refusal, version marker |
| Code | `core/errors.py` — error model, code namespace, remediation |
| Code | `core/logging.py` — structlog with correlation IDs |
| Code | `core/lifecycle.py` — `Service` protocol, manager, draining shutdown, executor pool |
| Code | `core/health.py` — readiness/liveness |
| Artifact | `static/css/app.css`, Cornerstone bundle — committed |
| Artifact | `package.json` + lockfile |
| Artifact | Vendored asset manifest with versions and licences |
| Artifact | CI stale-asset check |
| Document | Cornerstone3D bundling spike report |
| Suite | Path traversal rejection; non-loopback bind refusal; config-source locking |

## Phase 05 — Domain Model

| Class | Deliverable |
|-------|-------------|
| Code | `shared/value_objects.py` — frozen dataclasses with invariants |
| Code | Aggregates: Association, AssociationPair, Capture, Replay, Report |
| Code | `shared/errors.py` — domain error taxonomy |
| Code | `core/clock.py`, `core/ids.py` — protocols |
| Code | `tests/doubles/` — controllable wall clock, manual monotonic, seeded UUIDv7 |
| Artifact | import-linter contract banning `time.` / `uuid.` outside `core/` |
| Suite | Value-object invariants; both clock halves independently freezable |

## Phase 06 — Storage

| Class | Deliverable |
|-------|-------------|
| Code | `index.db` schema — projections, capture index, event window |
| Code | `app.db` schema — jobs, audit, bookmarks |
| Code | Connection policy (WAL, busy_timeout, single writer) and migrations |
| Code | Row↔domain mapping layer |
| Code | Capture format writers: `manifest.json`, `events.jsonl`, `pdus.jsonl`, `objects/` |
| Code | `.lpcap` pack/unpack with format version |
| Code | Index rebuild and capture discovery |
| Decision | ADR-0029 — cascade semantics for cross-capture projections |
| Document | Capture format specification |
| Suite | Rebuild byte-comparison; digest tamper detection; cascade behaviour |

## Phase 07 — Event System

| Class | Deliverable |
|-------|-------------|
| Code | `shared/events.py` — current canonical envelope (all five ADR extensions) |
| Code | Payload model registry keyed `(event_name, event_version)` |
| Code | `core/bus.py` — loop-owned bus, thread-safe ingress, ingress contract |
| Code | Sequencer, split backpressure, per-subscriber budget, clock anomaly detection |
| Artifact | **Generated versioned event catalog** |
| Suite | Ordering under threaded storm; sequence gap matches `EventsDropped`; unknown-field round-trip; `origin` required |

## Phase 08 — REST API

| Class | Deliverable |
|-------|-------------|
| Code | `web/api/v1/` — resource routes for captures, studies, associations, events, operations, settings, health |
| Code | Error responses, pagination policy, filtering |
| Code | Access-control seams: read-only, Host allowlist, origin checks, trusted proxies, rate limits |
| Code | Client-asserted event endpoint |
| Code | `cli/` — API client plus offline one-shot commands |
| Artifact | Published OpenAPI document |
| Document | CLI command surface specification |
| Suite | Read-only single-seam coverage; Host and origin rejection |

## Phase 09 — WebSocket

| Class | Deliverable |
|-------|-------------|
| Code | `/api/v1/events/stream` — JSON envelopes, topic subscriptions |
| Code | `/ws/ui` — HTML fragment adapter in `web/` |
| Code | Shared Jinja partials serving first paint **and** live update |
| Code | Coalescing governor with per-target policies |
| Code | Heartbeat, idle timeout, reconnection with subscription resume |
| Artifact | Published stream contract (asyncapi or equivalent) |
| Suite | 5,000-event burst within 100 ms; handshake origin rejection; drop accounting |

## Phase 10 — DICOM Networking

| Class | Deliverable |
|-------|-------------|
| Code | `associations/` — SCP listener, SCU client, bus ingress |
| Code | Relay core; pass-through negotiation; permissive standalone mode |
| Code | Service-agnostic passthrough with `UnrecognizedDimseObserved` |
| Code | Per-leg timing attribution |
| Code | Enrichment for C-ECHO, C-STORE, C-FIND, C-GET; C-MOVE progress recording |
| Code | Destination-AE interception mode |
| Code | PDU trace writer with message keying |
| Document | Deployment topology notes (feeding Phase 18) |
| Suite | Loopback C-STORE end to end; byte-fidelity of malformed traffic; bus-volume bound; PDU bus-bypass |

## Phase 11 — Capture Engine

| Class | Deliverable |
|-------|-------------|
| Code | Ring buffer service with events-only switch and retention exposure |
| Code | Capture sessions, retroactive promotion, partial marking |
| Code | Fidelity tier recording; clock anchor |
| Code | Crash recovery: torn-line discard, `Interrupted` marking, index re-derivation |
| Decision | ADR-0030 ratified — budgets promoted to release gates |
| Document | Capture and promotion user documentation |
| Suite | Kill-mid-capture; drain-on-SIGTERM; buffer capacity under sustained load |

## Phase 12 — Replay Engine

| Class | Deliverable |
|-------|-------------|
| Code | `replay/` — event replay, protocol replay, fidelity gate |
| Code | Replay provenance (`replay_id`, `replay_of_event_id`, linked correlation) |
| Code | Guardrails: dry-run, explicit target, allowlist, audit, exclusivity |
| Code | `core/jobs.py` — registry, durable audit, interruption sweep, cancellation |
| Artifact | Golden `.lpcap` fixture set covering the `01` §3 catalogue |
| Suite | Byte-comparable replay regression; every guardrail refusal; restart sweep |

## Phase 13 — Viewer

| Class | Deliverable |
|-------|-------------|
| Code | `studies/` decode pipeline, sidecar metadata, LRU cache, prefetch |
| Code | Frame endpoints; Cornerstone custom image loader |
| Code | Client-side W/L, zoom, pan, invert, cine |
| Code | Projection rebuild, per-instance provenance, partial marking, duplicate-UID finding |
| Code | Folder import as synthetic capture at `fidelity: objects` |
| Code | Workspace shell and panels: Metadata Inspector, Transfer Inspector, Event Timeline, Live Monitor, command palette, theming |
| Deferred | Log Console, Dashboard, Search, and notifications are additive views deferred per `phase-13-defer-audit.md` |
| Suite | Decode timing present in an exported report; partial-study never whole; W/L within budget; decode-failure explanation |

## Phase 14 — Analysis

| Class | Deliverable |
|-------|-------------|
| Decision | ADR-0028 — Analysis ownership and the Transfer Analysis boundary |
| Code | `analysis/` — condition registry, detection, finding model, rule engine |
| Code | Rule-set versioning; `analysis/` persistence |
| Code | Evidence linking in the UI |
| Code | Seed rule set — eight rule families per `01` §3 |
| Document | Condition catalogue with remediation text, citable in a vendor ticket |
| Suite | Purity (delete, re-run, identical); no finding in `events.jsonl`; client-asserted excluded |

## Phase 15 — Reports

| Class | Deliverable |
|-------|-------------|
| Code | `reports/` — Jinja templates, content assembly, background generation |
| Code | Redaction: tag profile, UID remapping, new-capture output, warnings |
| Code | Object-dropping export as default; pixel-bearing opt-in |
| Document | Handover workflow guide; redaction limitations stated plainly |
| Suite | Default-export carries no pixels; UID hierarchy survives; terminology audit |

## Phase 16 — Plugin SDK

| Class | Deliverable |
|-------|-------------|
| Code | `plugins/` — hook specs over contracts DTOs, manifest schema, loader |
| Code | Containment: exception isolation, time budget, compatibility gate, structural validation |
| Code | CLI install command; API list/enable/disable/inspect only |
| Code | Seed rules re-homed as bundled plugins on the public SDK |
| Artifact | Example plugin |
| Document | SDK guide, versioning scheme, deprecation window |
| Document | Extension point gap report from the seed-rule port |
| Suite | Raising plugin contained; slow plugin auto-disabled; no install route |

## Phase 17 — Observability

| Class | Deliverable |
|-------|-------------|
| Code | Event-derived metric registry and API exposure |
| Code | Per-service and per-plugin health |
| Code | Audit log covering every `12` §10 category |
| Code | Alerting thresholds; incident investigation support |
| Artifact | Metrics dashboard |
| Suite | Metric and event count agree by construction; `app.log` free of event mirror |

## Phase 18 — Production Hardening

| Class | Deliverable |
|-------|-------------|
| Suite | Performance suite against ratified budgets (startup, large study, throughput, memory, replay, concurrent clients) |
| Suite | Security review coverage: input validation, path containment re-verification, secret handling |
| Suite | Accessibility: keyboard-only primary workflows, contrast |
| Document | `19-glossary.md` reconciled with implementation vocabulary |
| Document | Deployment topology guide; operator guide; troubleshooting guide; user documentation |
| Artifact | Clean dependency vulnerability report, or recorded exceptions |

## Phase 19 — Packaging

| Class | Deliverable |
|-------|-------------|
| Artifact | Wheel and sdist including committed assets |
| Artifact | Docker image — non-root, one volume, exposure flag set |
| Document | Upgrade and migration notes; volume ownership contract |
| Suite | No-Node clean-machine install; no outbound request on page load; newer-data-dir refusal |

## Phase 20 — Release

| Class | Deliverable |
|-------|-------------|
| Suite | Interop matrix — DCMTK, dcm4che, Orthanc; transfer syntax coverage |
| Artifact | Published interop results with triaged failures |
| Document | Acceptance validation against `02-alt` §26 and `00` §11 |
| Document | Known-limitations statement |
| Document | Release notes, changelog, versioning scheme |

---

# 4. Standing artifacts

Regenerated continuously, not once. Each has a CI check that fails on drift.

| Artifact | Owner phase | Drift check |
|----------|-------------|-------------|
| Event catalog | 07 | Regenerated in CI; difference fails |
| OpenAPI document | 08 | Regenerated in CI; difference fails |
| Compiled CSS + Cornerstone bundle | 04 | Rebuilt in CI; difference fails |
| import-linter contracts | 02 | Enforced every run |
| Asset provenance manifest | 04 | Reviewed on dependency change |
| Condition catalogue | 14 | Generated from the registry |

The drift checks matter because each of these is a place where a change is otherwise
invisible: a Python contributor adding a Tailwind class gets a subtly wrong page, and a new
event without a catalog entry is discovered by a plugin author.

---

# 5. What is deliberately not delivered

Stated so absence is not read as oversight. Each needs its own ADR first.

pcap import · byte-exact and mock-peer replay · remote collectors · multi-user auth and
RBAC · plugin installation over the API · named config profiles · DIMSE-N enrichment ·
Prometheus exposition · PS3.15 de-identification profile · TLS termination inside the
application.

---

# 6. References

`01-work-breakdown-structure.md` · `02-phase-plan.md` · `04-milestones.md` ·
`07-definition-of-done.md` · `../adr/README.md`.
