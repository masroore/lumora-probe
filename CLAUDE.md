# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status: documentation-only

There is no implementation yet. The repo is `pyproject.toml`, a placeholder `main.py`,
and ~11.7k lines of specification under `docs/`. Per `docs/planning/08-implementation-order.md`
§6, work starts at Phase 01 Stage 1, task **T-01-01-02** (write ADR-0027 to settle which
document is the authoritative PRD — `02-product-requirements-document.md` and
`Lumora-Probe-PRD.md` both exist and conflict). Do not start writing feature code before
that is resolved.

## What the product is

Lumora Probe is an engineering observability platform for DICOM network traffic — capture,
replay, analyze, troubleshoot. "Browser devtools for DICOM." Explicit non-goals
(`docs/architecture-baseline/00-project-charter.md` §6): it is not a diagnostic
workstation, PACS archive, RIS/EMR, reporting system, 3D/MPR viewer, or AI diagnostic
platform. Reject scope creep toward clinical use.

## Read the docs before changing a subsystem

Three layers, in precedence order:

1. `docs/adr/` — **the authoritative resolution layer.** 26 ADRs. Start at
   `docs/adr/README.md`, which indexes them and lists every recorded deviation from the
   baseline. Where an ADR contradicts a baseline document, the ADR wins.
2. `docs/architecture-baseline/` — 21 numbered documents, binding where specific and silent
   elsewhere (ADR-0001). Cited by number: `06` §9 = `06-event-driven-architecture.md` §9.
3. `docs/planning/` — WBS, phase plan, dependency graph, definition of done, risk register.

Deviating from a specific baseline statement requires a new ADR, not a code comment. The
ADRs already list nine topics that are **deferred pending their own ADR** (pcap import,
byte-exact replay, remote collectors, auth/RBAC, plugin install over API, config profiles,
DIMSE-N enrichment, Prometheus exposition, PS3.15 de-identification) — do not implement
these.

## Toolchain

`uv` + Hatchling, Python 3.13+. Ruff (format, lint, import order), BasedPyright (static
analysis), pytest + pytest-asyncio, import-linter for boundary contracts. FastAPI +
Uvicorn, Pydantic v2, pydantic-settings, structlog, orjson, SQLAlchemy **Core only — no
ORM** (`04` §6), pydicom + pynetdicom.

No build/test/lint command strings are pinned in the docs yet; `pyproject.toml` has no dev
dependencies or tool config. Establishing these is Phase 02/03 work. Once they exist,
record them here.

Frontend: HTMX + Alpine.js + Chart.js + Tabulator vendored as single-file dists;
Cornerstone3D and Tailwind CSS 4 are the only two things needing a Node build. Built assets
(`static/css/app.css`, the Cornerstone bundle) are **committed** and shipped in the sdist —
CI rebuilds them and fails on drift (ADR-0025). Installing or running the app must never
require Node.

## Package layout and import boundaries

Top-level package `lumora/` (ADR-0012). Module-first slices, not layer-first directories:

```
lumora/core/          bus, config, ids, clock, errors, storage primitives
lumora/shared/        DICOM value objects, event envelope + payload registry
lumora/associations/  captures/  replay/  studies/
lumora/analysis/      reports/   plugins/  settings/
lumora/web/           Jinja/HTMX templates, view composition, UI socket adapter
```

Each slice holds `domain.py`, `service.py`, `repository.py`, `api.py`, and a public
`contracts.py`. Views with no state of their own (Dashboard, Live Monitor, Event Timeline,
Metadata Inspector, Viewer) live in `web/` over existing slices — they get no package.

Enforced by import-linter:

- `core` imports no slice; `shared` imports only `core`.
- A slice may import `core`, `shared`, and other slices' `contracts.py` — nothing else.
- `web` imports slices; no slice imports `web`.
- No `domain.py` imports FastAPI, SQLAlchemy, or Jinja.
- No `time.` or `uuid.` import outside `core/` (ADR-0022).
- Cross-slice reads go through the bus or a contract-typed service call, never another
  slice's repository. Two slices may share a SQLite file but never a repository object.

## Concurrency model (ADR-0002, ADR-0007)

Single process. The asyncio loop owns the event bus and is the sole authority for event
ordering. There is exactly **one thread boundary in the system**: pynetdicom's
thread-per-association threads publish via `loop.call_soon_threadsafe` onto a bounded
ingress queue. Everything downstream is loop-side.

- Blocking work — dataset parse, pixel decode, SQLite writes, report generation — runs in an
  explicit executor, never on the loop.
- Repository interfaces are `async def`.
- The bus supports async subscribers (awaited) and sync subscribers (called inline,
  contractually non-blocking). Each subscriber has a per-event time budget; breaching it
  raises a warning event.
- Backpressure splits by purpose: the capture/persistence path **never drops**; UI/WebSocket
  channels use bounded drop-oldest queues plus an `EventsDropped` counter surfaced in the UI.
- Shutdown drains: stop accepting associations → drain ingress → flush/fsync the capture
  writer → close, within a bounded grace period. Missing the deadline records
  `CaptureInterrupted` in the manifest.
- The `lumora` CLI is a client over `/api/v1` only — never a second bus or SQLite writer.
  The exception is one-shot offline commands like `lumora capture inspect <file>`.
- The DICOM listener binds **11112**, not 104, so it never needs root.

## Time and ordering (ADR-0017)

Three fields, one job each. Getting this wrong is a correctness bug, not a style issue.

- `occurred_at` — wall clock UTC. Display and cross-capture correlation only. **Never** used
  for ordering or arithmetic. This overrides `06` §9, which says the opposite.
- `monotonic_ns` — from `time.monotonic_ns()`, capture-relative. All durations and gaps.
- `sequence` — per-capture, gap-free integer assigned by the loop-owned sequencer at publish
  time. The only authority for order. Gap-free is the point: a jump in `events.jsonl` proves
  a dropped event, which makes `EventsDropped` auditable.

The manifest stores one wall+monotonic anchor pair at capture start. Wall/monotonic
divergence past a threshold emits `ClockAnomalyDetected` rather than corrupting data.

## Domain vs boundary models (ADR-0006)

- Domain: plain Python, framework-free. Value objects are
  `@dataclass(frozen=True, slots=True)` with invariants in `__post_init__`. Aggregates are
  ordinary classes with behavior and no base class. Aggregates do **not** inherit
  `BaseModel` — `04` §4's "domain validation via Pydantic" means Pydantic is the approved
  boundary validator, nothing more.
- Boundaries: Pydantic v2 — REST/WebSocket schemas, config, the event envelope and its
  payload catalog, plugin manifests, capture manifests.
- Repositories do explicit hand-written row↔domain mapping.
- The envelope is a versioned wire contract with a payload registry keyed by
  `(event_name, event_version)`. Unknown fields are **preserved, not stripped** — persistence
  is byte-faithful.
- Plugins see boundary types only, never aggregates.

Envelope required fields (`06` §6): `event_id`, `event_name`, `event_version`, `occurred_at`,
`correlation_id`, `aggregate_type`, `aggregate_id`, `producer`, `payload`; optional
`causation_id`, `severity`. Delivery is at-least-once — subscribers must be idempotent.
Ordering is guaranteed within one aggregate and one capture session, never globally.

Prefer Publisher → Bus → Subscribers over Module → Module → Module chains (`03` §6).

## Evidence integrity

This is the project's spine and the definition of done enforces it (`docs/planning/07-definition-of-done.md` §2):

- Every event carries `origin`. Client-asserted events (e.g. `ImageDisplayed` from the
  viewer) are admitted but quarantined — they must never feed analysis, timing, or replay
  fidelity (ADR-0016).
- Nothing inferred is written to `events.jsonl`. Observed **conditions** and inferred
  **findings** are physically separate stores (ADR-0018); findings live in `analysis/` and
  are regenerable.
- Never claim anonymization, de-identification, or PS3.15 compliance. Redaction is honest
  and partial; object-dropping is the default handover (ADR-0026).
- Detectable failures are reported with cause and remediation, never swallowed. A capability
  that cannot be delivered is **refused with an explanation**, never silently degraded.

## Storage

One root, `LUMORA_DATA_DIR`, OS-conventional default (XDG / `~/Library/Application Support`
/ `%APPDATA%`). Everything derives from it: `index.db`, `app.db`, `captures/`,
`ringbuffer/`, `reports/`, `logs/`, `plugins/`, `settings.toml` (ADR-0011). SQLite in WAL
mode, single writer, `busy_timeout` set, and **refused on network filesystems**. A `version`
marker in the root; a data dir written by a newer version is refused.

A capture is a directory, not a blob (ADR-0004):

```
captures/<uuid7>/
  manifest.json     identity, provenance, fidelity tier, digests, clock anchor
  events.jsonl      canonical envelopes, verbatim, append-only
  pdus.jsonl        protocol trace, present at fidelity >= protocol
  objects/<sha256>  content-addressed received datasets
  logs/
  analysis/         regenerable findings
```

`.lpcap` is that directory zipped (deflate) — the interchange form. Dropping one into
`captures/` makes it appear.

The two databases differ in authority (ADR-0023):

- `index.db` — study/series/instance projections, capture index, rolling event window.
  **Derived; droppable and rebuildable at any time.** If the index and the capture directory
  disagree, the directory wins.
- `app.db` — job history, audit log, bookmarks. Authoritative, and the only file needing
  backup.

Study/Series/Instance are projections over captures, not top-level aggregates (ADR-0013) —
the demotion exists to keep the system from becoming the PACS archive the Charter forbids.

## HTTP and WebSocket surface

No authentication in v1 (ADR-0009); TLS is a reverse-proxy concern. Binding is loopback by
default and a non-loopback bind requires explicit acknowledgment via `--trust-network`
(ADR-0010). Read-only is a server-wide mode behind a single enforcement seam, not RBAC.
When adding a network-exposed surface, keep that gate intact.

Two sockets, deliberately not one (ADR-0019):

- `/api/v1/events/stream` — canonical JSON envelopes, topic subscription. Part of the API
  contract; consumed by CLI, plugins, integrations.
- `/ws/ui` — server-rendered HTML fragments for HTMX, subscribed by mounted view.
  A presentation adapter in `web/`, explicitly **not** an API contract.

Both are fed from one bus subscription through a shared coalescing governor (~100ms flush;
counters aggregate, status is latest-wins, timeline appends with a cap). Fragments use
targeted out-of-band swaps. Viewer interaction (window/level, zoom, pan, cine) is the one
intentional no-round-trip exception — the server decodes pixels, Cornerstone3D only renders
(ADR-0015).

## Configuration tiers (ADR-0020)

Precedence: env > `.env` > TOML/YAML > defaults. Validation failure at startup **aborts**,
naming the offending key and its source — never falls back to a default.

- **Startup config** (bind address, `--trust-network`, data/capture roots, ports, executor
  sizing): file and env only, immutable. A live change attempt returns a structured error
  naming the setting, its source, and the restart requirement — refused, not queued.
- **Runtime settings** (ring buffer cap/retention, decode cache size, AE/IP allowlist,
  read-only mode, rule toggles, theme): editable via API/UI, applied live, persisted to
  app-written `settings.toml`.

Every setting reports a `source` of `default` | `file` | `env` | `runtime`; env/file-pinned
settings render locked with the source named. Changes emit `ConfigurationChanged` with
old/new values, redacted where sensitive.

## Background operations (ADR-0023)

In-memory execution, durable audit record, **never auto-resumed**. Anything `running` at
startup becomes `Interrupted` with a reason. Progress rides the event bus — no second
transport; `/api/v1/operations/{id}` reads the same registry. Concurrency is bounded per job
type and protocol replay is exclusive: refused, not queued, if one is already running.
Cancellation is cooperative and must report how many instances were sent and confirmed.

## Testing (ADR-0022 — overrides `13` §4)

Not a unit-heavy pyramid. Weight sits at **component and integration** level, where this
system's bugs actually live.

- Thin unit layer: genuinely pure logic only (value-object invariants, rule evaluation,
  envelope serialization).
- Bulk at component level: real SQLite, real pydicom, real filesystem, real bus — faking only
  the clock and the ID source. Real pynetdicom loopback for the DICOM edge.
- Thin end-to-end over HTTP for the workflows `13` §7 names.
- `Clock` and `IdGenerator` are `core` protocols, always injected, never called directly.
  Doubles: controllable wall clock, manually advanced monotonic counter, seeded deterministic
  UUIDv7 sequence. The import-linter ban on `time.`/`uuid.` outside `core/` is what enforces
  this — so tests advance a counter instead of sleeping.
- `.lpcap` golden fixtures are the regression backbone: replay must produce a byte-comparable
  event stream and finding set.
- Test DICOM data is **synthetic only**, generated by pydicom via a reviewable script. Never
  real patient data, not even de-identified — stricter than `13` §14.
- Required adversarial tests: kill mid-capture (torn trailing line discarded, capture marked
  `Interrupted`), and UI channel saturation (the `sequence` gap must equal the
  `EventsDropped` count). Any new concurrency/ordering/drop/crash behavior needs its own
  adversarial test.
- Interop against DCMTK / dcm4che / Orthanc is opt-in and scheduled, not in the default gate.

## Definition of done

`docs/planning/07-definition-of-done.md` is the checklist and it is not advisory — task-level
gates are explicitly non-waivable. Before calling a task complete: import-linter passes,
tests at the prescribed layer pass (a skip is not a pass), no new dependency without an ADR,
contract changes regenerate their artifact (OpenAPI / event catalog / stream contract), new
terms land in `19-glossary.md`, and any deviation is recorded in an ADR **before** merge.

## Plugins (ADR-0021)

Plugins are trusted in-process code. The manifest is disclosure, not enforcement — the docs'
"enforced plugin capabilities" (`10` §13, `12` §11) is impossible in-process, so build what
is actually enforceable and do not pretend otherwise in UI or docs.
