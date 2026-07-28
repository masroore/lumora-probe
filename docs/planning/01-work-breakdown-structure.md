# 01 — Work Breakdown Structure

> **Project:** Lumora Probe
>
> **Document:** Work Breakdown Structure
>
> **Status:** Planning Baseline
>
> **Audience:** Engineering, QA, Architects, Claude Code, Codex

---

# 1. Purpose

This document decomposes Lumora Probe from an empty repository to a production release,
at a granularity where each task is implementable in one focused effort by one agent.

Read `00-architecture-review-findings.md` first, and `02-phase-plan.md` for the phase
definitions and entry/exit criteria this document assumes.

---

# 2. Decomposition model

```
Epic          E-n     Major capability area, spans phases
 └ Capability C-nn    Coherent subsystem
   └ Feature  F-nnn   User- or contract-visible behaviour
     └ Work Package  WP-pp-nn    Phase-scoped unit of review (pp = phase)
       └ Task        T-pp-nn-nn  One focused implementation effort
```

`WP-07-03` is Phase 07's third work package; `T-07-03-02` is its second task.

## 2.1 Task attributes

Every task carries eleven attributes. Rather than repeat all eleven in prose for
~210 tasks, tasks are tabulated with the attributes that vary, and the invariant ones are
stated once here.

| Attribute | Where it lives |
|-----------|----------------|
| Identifier | Table column `ID` |
| Title | Table column `Task` |
| Objective / description | Table column `Task` plus the work package preamble |
| Dependencies | Table column `Deps` (`—` means the work package's own entry conditions suffice) |
| Complexity | Table column `Cx` — XS/S/M/L/XL |
| Priority | Table column `P` — P0 blocking, P1 required for phase exit, P2 deferrable within phase |
| Affected modules | Table column `Module`, using ADR-0012 slice names |
| Acceptance criteria | Table column `Acceptance` |
| Deliverables | §2.2 defaults, plus anything named in `Acceptance` |
| Documentation updates | §2.3 rule |
| Testing requirements | §2.4 rule, plus `Acceptance` where a specific test is mandated |
| Parallel safety | Table column `∥` — `Y` safe to run concurrently with siblings, `N` serialise |

## 2.2 Default deliverables

Unless a task's `Acceptance` says otherwise, every task delivers: implementation, tests at
the layer §2.4 prescribes, docstrings on public surfaces, and any ADR-required
documentation. Tasks that add a dependency also deliver the `pyproject.toml` change and a
licence note (`04` §14).

## 2.3 Documentation rule

`18` §13 requires documentation to move with code. Concretely:

- A task changing a REST or WebSocket contract updates the generated OpenAPI/asyncapi
  artifact.
- A task adding or changing an event updates the generated catalog (F-04).
- A task introducing a term updates `19-glossary.md` (F-05 tracks the backlog).
- A task deviating from the baseline requires an ADR **before** merge, per ADR-0001.

## 2.4 Testing rule

Per ADR-0022, weighted to component level as a deliberate deviation from `13` §4:

| Task touches | Required tests |
|--------------|----------------|
| Pure logic (value objects, rules, serialization) | Unit |
| A slice service or repository | Component, real SQLite, real filesystem, real bus, faked `Clock`/`IdGenerator` |
| The DICOM edge | Component against real pynetdicom on loopback |
| An HTTP or WS contract | Thin end-to-end over the transport |
| Capture or replay semantics | Golden `.lpcap` regression |
| Concurrency, ordering, drop or crash behaviour | Explicit adversarial test — these are unverifiable promises otherwise |

Complexity is engineering size, not duration: **XS** trivial · **S** one sitting ·
**M** focused effort · **L** needs decomposition on contact · **XL** must be split before
starting.

---

# 3. Epic map

| Epic | Title | Phases | Capabilities |
|------|-------|--------|--------------|
| E-1 | Foundation and Governance | 01–03 | C-01 … C-03 |
| E-2 | Platform Core | 04–07 | C-04 … C-07 |
| E-3 | Interfaces | 08–09 | C-08, C-09 |
| E-4 | DICOM Observation | 10–11 | C-10, C-11 |
| E-5 | Investigation | 12–15 | C-12 … C-15 |
| E-6 | Extensibility and Operations | 16–17 | C-16, C-17 |
| E-7 | Release Readiness | 18–20 | C-18 … C-20 |

One capability per phase, so `C-nn` and phase `nn` correspond throughout.

---

# 4. Epic E-1 — Foundation and Governance

## C-01 — Architecture governance (Phase 01)

### WP-01-01 — Close the decision gaps

The four findings that need decisions, plus the phase-numbering reconciliation. ADR-0027
is P0 because Charter §12 precedence is unresolved until it lands, and every requirement
trace depends on knowing which PRD is authoritative.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-01-01-01 | Publish architecture review findings | — | L | P0 | docs | N | 21 baseline docs and 26 ADRs assessed; findings classified RESOLVED/OPEN/WATCH; no baseline file modified |
| T-01-01-02 | ADR-0027 — authoritative PRD | T-01-01-01 | S | P0 | docs | N | Names one file as the PRD; explains the Charter §12 consequence; ADR README updated to disambiguate `02` |
| T-01-01-03 | ADR-0030 — non-functional budgets (draft) | T-01-01-01 | M | P1 | docs | Y | Provisional budgets derived from ADR-0014's figures; ratification task created for Phase 11 |
| T-01-01-04 | Phase numbering reconciliation | T-01-01-01 | S | P0 | docs | Y | Seven ADR phase citations mapped; three drifts recorded; no ADR rewritten (`17` §12) |
| T-01-01-05 | Gap register with owning phases | T-01-01-01 | S | P1 | docs | Y | Every OPEN finding and undefined-behaviour item has an owning phase and appears in this WBS |

## C-02 — Repository structure (Phase 02)

### WP-02-01 — Project skeleton

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-02-01-01 | `pyproject.toml` with uv + Hatchling | — | S | P0 | root | N | `uv sync` succeeds clean; Python 3.13+ pinned (`04` §3) |
| T-02-01-02 | Nine ADR-0012 slices with five-file stubs | T-02-01-01 | M | P0 | all | N | `core`, `shared`, `associations`, `captures`, `replay`, `studies`, `analysis`, `reports`, `plugins`, `settings`, `web` present; each slice has `domain/service/repository/api/contracts` |
| T-02-01-03 | Repository layout per `18` §4 | T-02-01-01 | XS | P1 | root | Y | `tests/`, `docs/`, `plugins/`, `scripts/` present |
| T-02-01-04 | Licence, README, CONTRIBUTING | T-02-01-01 | S | P2 | docs | Y | Contribution flow states the ADR requirement for deviations |

### WP-02-02 — Machine-enforced boundaries

ADR-0012's central claim is that boundaries are enforced rather than documented. A guard
nobody has seen fail is not a guard, hence T-02-02-02.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-02-02-01 | import-linter contracts, all six | T-02-01-02 | M | P0 | root | N | `core` imports no slice; `shared` imports only `core`; slices reach others only via `contracts.py`; nothing imports `web`; no `domain.py` imports FastAPI/SQLAlchemy/Jinja |
| T-02-02-02 | Prove each contract fails | T-02-02-01 | S | P0 | tests | N | A deliberate violation per contract is shown to fail the check; test asserts the failure |

## C-03 — Quality gate (Phase 03)

### WP-03-01 — CI and gates

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-03-01-01 | CI pipeline skeleton | T-02-02-01 | M | P0 | ci | N | Runs on push and PR; fails the build on any gate |
| T-03-01-02 | Format and lint gates | T-03-01-01 | S | P0 | ci | Y | ruff format and check per `13` §15; `18` §5 conventions |
| T-03-01-03 | Static analysis gate | T-03-01-01 | M | P0 | ci | Y | Type checking on `core`/`shared` at minimum; import-linter wired in |
| T-03-01-04 | Coverage reporting | T-03-01-01 | S | P1 | ci | Y | Reported per slice; no global threshold that rewards testing mappers (ADR-0022 rationale) |
| T-03-01-05 | Dependency vulnerability scan | T-03-01-01 | S | P1 | ci | Y | `13` §13; failures triaged not ignored |

### WP-03-02 — Test harness

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-03-02-01 | pytest + pytest-asyncio + markers | T-03-01-01 | M | P0 | tests | N | Marker taxonomy: unit, component, dicom, e2e, interop, slow; dev-only deps recorded per ADR-0022 §6 |
| T-03-02-02 | Synthetic DICOM fixture generator | T-03-02-01 | L | P0 | tests | N | Generated by pydicom **by script**; no real patient data, not even de-identified (ADR-0022 §3); fixtures reviewable as code |
| T-03-02-03 | Interop suite skeleton, non-gating | T-03-02-01 | M | P2 | tests | Y | DCMTK/dcm4che/Orthanc containers; marked and **scheduled**, kept out of the default gate (ADR-0022 §4) |
| T-03-02-04 | Golden `.lpcap` harness scaffold | T-03-02-02 | M | P1 | tests | Y | Compare-by-bytes helper ready for Phase 12 to populate |

### WP-03-03 — Threading spike

Pulled to Phase 03 deliberately. ADR-0002 defers it to Phase 11, but ADR-0007's ingress
design depends on the answer and Phase 10 cannot be designed without it. The question is
empirical and needs no capture engine — see `00-architecture-review-findings.md` §6.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-03-03-01 | pynetdicom threading spike | T-03-02-02 | L | P0 | spike | N | Establishes empirically which thread runs `EVT_C_STORE`, what blocks, what the ingress contract must accept; written up and either confirms ADR-0002 or triggers an amendment |
| T-03-03-02 | Provisional budget derivation | T-01-01-03 | M | P1 | docs | Y | Event volume, PDU volume, ring buffer sizing turned into measurable provisional thresholds |

---

# 5. Epic E-2 — Platform Core

## C-04 — Configuration and data root (Phase 04)

### WP-04-01 — Two-tier configuration

ADR-0020's substance is that a setting pinned by env must render as *locked with the
source named*, never as an editable field that discards writes. That makes provenance a
first-class attribute, not a debugging aid.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-04-01-01 | Startup config model, Pydantic | T-03-01-01 | M | P0 | core | N | Precedence env > `.env` > TOML/YAML > defaults (`04` §4); immutable after start |
| T-04-01-02 | Runtime settings in `settings.toml` | T-04-01-01 | M | P0 | settings | N | App-written, under `LUMORA_DATA_DIR`, **separate from the index** — else the first rebuild resets everyone's config (ADR-0020) |
| T-04-01-03 | Provenance tagging | T-04-01-02 | M | P0 | settings | N | Every setting reports `default`/`file`/`env`/`runtime` |
| T-04-01-04 | Refuse restart-required changes | T-04-01-03 | S | P0 | settings | Y | Structured error naming setting, current source, restart requirement; accept-and-defer explicitly not implemented |
| T-04-01-05 | Startup validation failure path | T-04-01-01 | S | P0 | core | Y | Aborts naming the offending key **and its source**; never silently defaults |
Note: `ConfigurationChanged` emission (ADR-0020, `12` §10) is **not** in this work package
— it needs the event taxonomy, which arrives in Phase 07. It is scheduled as T-07-01-07 to
avoid a forward dependency.

### WP-04-02 — Data directory

Task T-04-02-04 is the whole exploit chain in a v1 with no authentication: a `capture_id`
of `../../etc` reaching `open()`.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-04-02-01 | `LUMORA_DATA_DIR` resolution | T-04-01-01 | M | P0 | core | N | XDG / `Library/Application Support` / `%APPDATA%`; single env override; never defaults inside the source tree |
| T-04-02-02 | Independently overridable captures root | T-04-02-01 | S | P0 | core | Y | Relocatable; safe because the index is rebuildable |
| T-04-02-03 | Additional read-only capture roots | T-04-02-02 | M | P1 | core | Y | A handed-over `.lpcap` is browsable without import — the `01` §8 vendor workflow |
| T-04-02-04 | Path containment enforcement | T-04-02-01 | M | P0 | core | N | UUIDv7 format check → `resolve()` → assert under an allowed root; traversal test proves rejection |
| T-04-02-05 | Network filesystem refusal | T-04-02-01 | M | P0 | core | Y | Detected network path for `index.db`/`app.db` is **refused with explanation**, not warned about and corrupted later |
| T-04-02-06 | Data directory version marker | T-04-02-01 | S | P1 | core | Y | Newer-version directory refused, not mangled |

### WP-04-03 — Errors, logging, lifecycle

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-04-03-01 | Structured error model + code namespace | T-03-01-01 | L | P0 | core | N | Carries context and remediation guidance (`03` §12); allocation rule documented (U-03); silent failure impossible by construction |
| T-04-03-02 | structlog with correlation IDs | T-04-03-01 | M | P0 | core | N | Machine-readable, redaction hooks (`14` §5); IDs shared with events (`14` §8) |
| T-04-03-03 | `Service` protocol | T-04-03-01 | M | P0 | core | N | start/stop/health over loop tasks, threads, executors, workers (ADR-0007) |
| T-04-03-04 | Lifecycle manager | T-04-03-03 | L | P0 | core | N | Ordered startup, reverse-ordered shutdown, per-service health reporting |
| T-04-03-05 | Draining shutdown sequence | T-04-03-04 | L | P0 | core | N | Stop accepting → drain ingress → flush and fsync → close; bounded grace period |
| T-04-03-06 | Health readiness/liveness split | T-04-03-03 | M | P1 | core | Y | Distinguished per service (U-06, `14` §9) |
| T-04-03-07 | Executor pool management | T-04-03-03 | M | P0 | core | N | Blocking work never on the loop (ADR-0002); sizing configurable |

### WP-04-04 — Network exposure gate

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-04-04-01 | Loopback default bind | T-04-01-01 | S | P0 | core | N | `127.0.0.1` unless acknowledged (ADR-0010) |
| T-04-04-02 | Exposure acknowledgment gate | T-04-04-01 | M | P0 | core | N | Non-loopback without `--trust-network` **refuses to start and explains why**; no credential introduced |

### WP-04-05 — Asset pipeline

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-04-05-01 | Cornerstone3D bundling spike | T-02-01-03 | L | P0 | web | N | Confirms the bundle covers the **rendering path only** — no DICOM parser, no WASM codecs (ADR-0015, ADR-0025) |
| T-04-05-02 | Tailwind 4 build | T-04-05-01 | M | P0 | web | N | `package.json` + lockfile; output committed |
| T-04-05-03 | Vendor single-file libraries | T-02-01-03 | S | P0 | web | Y | HTMX, Alpine, Chart.js, Tabulator vendored locally; **no CDN** (ADR-0009 no outbound telemetry) |
| T-04-05-04 | CI stale-asset check | T-04-05-02 | M | P0 | ci | N | CI rebuilds and fails on difference — a Python contributor adding a class gets a hard failure, not a subtly wrong page |
| T-04-05-05 | Asset provenance manifest | T-04-05-03 | S | P1 | web | Y | Versions and licences listed (`04` §14, `13` §13) |
| T-04-05-06 | Inline SVG icon helper | T-04-05-03 | S | P2 | web | Y | Lucide icons rendered by Jinja with no JavaScript |

## C-05 — Domain model (Phase 05)

### WP-05-01 — Value objects and aggregates

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-05-01-01 | DICOM value objects | T-04-03-01 | L | P0 | shared | N | `@dataclass(frozen=True, slots=True)`, invariants in `__post_init__`: AE title, UIDs, transfer syntax, presentation context (ADR-0006) |
| T-05-01-02 | Association aggregate | T-05-01-01 | M | P0 | associations | N | Lifecycle per `07` §12; no framework import |
| T-05-01-03 | AssociationPair aggregate | T-05-01-02 | L | P0 | associations | N | First-class per ADR-0003; downstream leg, Probe hop, upstream leg attributed **separately** |
| T-05-01-04 | Capture aggregate | T-05-01-01 | M | P0 | captures | Y | `Created → Running → Stopping → Completed → Archived` plus `Interrupted` |
| T-05-01-05 | Replay aggregate | T-05-01-01 | M | P0 | replay | Y | Mode, fidelity requirement, target, dry-run flag |
| T-05-01-06 | Report aggregate | T-05-01-01 | S | P1 | reports | Y | Rule-set version recorded (ADR-0018) |
| T-05-01-07 | Domain error taxonomy | T-04-03-01 | M | P0 | shared | N | Invariant violations raise domain errors, **never** `ValidationError` — Pydantic's vocabulary must not leak into an engineering-facing error model (ADR-0006) |

### WP-05-02 — Injected clock and identity

The single most leverage-per-line work package in the project: without it every test
asserting on an event is non-deterministic, and retrofitting is a whole-codebase sweep.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-05-02-01 | `Clock` protocol | T-04-03-01 | M | P0 | core | N | Exposes **both** wall and monotonic — ADR-0017's split is meaningless if only one can be frozen |
| T-05-02-02 | `IdGenerator` protocol | T-04-03-01 | S | P0 | core | N | UUIDv7 generation behind an interface |
| T-05-02-03 | Deterministic test doubles | T-05-02-01, T-05-02-02 | M | P0 | tests | N | Controllable wall clock, manually advanced monotonic counter, seeded UUIDv7 sequence |
| T-05-02-04 | import-linter ban on `time.`/`uuid.` | T-05-02-03 | S | P0 | ci | N | Banned outside `core/`; enforced rather than remembered (ADR-0022 §1) |

## C-06 — Storage (Phase 06)

### WP-06-01 — Database schemas

The split is physical and load-bearing: `index.db` must be droppable at any time, so
anything not re-derivable from captures cannot live there.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-06-01-01 | `index.db` schema | T-05-01-01 | L | P0 | core | N | Study/series/instance projections, capture index, rolling event window; every table re-derivable (ADR-0023) |
| T-06-01-02 | `app.db` schema | T-05-01-01 | M | P0 | core | N | Job history, audit log, bookmarks — authoritative, the only file needing backup |
| T-06-01-03 | SQLite connection policy | T-06-01-01 | M | P0 | core | N | WAL, `busy_timeout`, single writer (ADR-0011) |
| T-06-01-04 | Migration approach | T-06-01-02 | M | P1 | core | Y | `app.db` migrated; `index.db` recreated rather than migrated (ADR-0004 consequence) |
| T-06-01-05 | Concurrency spike | T-06-01-03 | M | P1 | spike | Y | Concurrent readers with one writer under load; informs pool sizing |

### WP-06-02 — Capture package format

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-06-02-01 | `manifest.json` model | T-05-01-04 | L | P0 | captures | N | Identity, provenance, fidelity, digests, clock anchor, partial flag, client-asserted count |
| T-06-02-02 | `events.jsonl` append-only writer | T-06-02-01 | L | P0 | captures | N | Canonical envelopes **verbatim** (`06` §16); crash-tolerant; fsync policy explicit |
| T-06-02-03 | Content-addressed object store | T-06-02-01 | L | P0 | captures | N | SHA-256 filenames; digest list in manifest; re-sent instances deduplicate |
| T-06-02-04 | `pdus.jsonl` writer | T-06-02-01 | M | P0 | captures | N | Minimal fields, **no envelope**, never on the bus (ADR-0014) |
| T-06-02-05 | `.lpcap` pack and unpack | T-06-02-03 | M | P0 | captures | N | Zip/deflate; directory is the working form |
| T-06-02-06 | `.lpcap` format version | T-06-02-05 | S | P0 | captures | Y | Reader forward-compatibility rule stated (U-10) |
| T-06-02-07 | Integrity verification | T-06-02-03 | M | P1 | captures | Y | Digest mismatch detected and reported (`11` §11) |

### WP-06-03 — Repositories and index rebuild

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-06-03-01 | Row↔domain mapping layer | T-06-01-01, T-05-01-01 | L | P0 | core | N | Hand-written, explicit, greppable (ADR-0006); `async def` interfaces (ADR-0002) |
| T-06-03-02 | Capture repository | T-06-03-01 | M | P0 | captures | N | Index entries only; directory is the source of truth |
| T-06-03-03 | Index rebuild from directories | T-06-03-02 | L | P0 | captures | N | Delete `index.db`, rebuild, **byte-compare** the projection |
| T-06-03-04 | Capture discovery | T-06-03-03 | M | P0 | captures | Y | Dropping a `.lpcap` into the folder makes it appear |
| T-06-03-05 | Retention policy semantics | T-06-03-02 | M | P1 | captures | Y | Configurable beyond the ring buffer (U-05, `11` §10) |
| T-06-03-06 | ADR-0029 + cascade implementation | T-06-03-03 | L | P0 | studies | N | Decides and implements bookmark/finding/report behaviour when one of three captures backing a study is deleted (F-08) |

## C-07 — Event system (Phase 07)

### WP-07-01 — Envelope and registry

The envelope in `06` §6 is five ADRs out of date. T-07-01-01 establishes the current one
in code; T-07-01-05 makes it discoverable so eight slices do not each infer it.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-07-01-01 | Canonical envelope, current | T-05-02-03 | L | P0 | shared | N | `06` §6 plus `origin` (0016), `monotonic_ns` + `sequence` (0017), `replay_id`/`replay_of_event_id` (0005); Pydantic, versioned |
| T-07-01-02 | Payload model registry | T-07-01-01 | L | P0 | shared | N | Keyed `(event_name, event_version)`; unknown pair handled explicitly |
| T-07-01-03 | Event category taxonomy | T-07-01-01 | M | P0 | shared | N | Ten categories of `06` §5; exactly one per event; naming rules of `06` §7 enforced by test |
| T-07-01-04 | Unknown-field preservation | T-07-01-02 | M | P0 | shared | N | Preserved not stripped; raw bytes retained on the capture-write path (`06` §3, §16) |
| T-07-01-05 | Generated event catalog | T-07-01-02 | M | P0 | docs | N | Generated from code, versioned, published as an artifact (F-04) |
| T-07-01-06 | `origin` required-field enforcement | T-07-01-01 | S | P0 | shared | N | Absence is a **validation error**, not an assumed-trusted event (ADR-0016) |
| T-07-01-07 | `ConfigurationChanged` emission | T-07-01-03, T-04-01-03 | S | P1 | settings | Y | Old and new values, sensitive fields redacted (`12` §10); lets a capture's provenance be cross-referenced against the settings in force |

### WP-07-02 — Bus and sequencer

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-07-02-01 | Loop-owned bus | T-07-01-01, T-04-03-03 | XL | P0 | core | N | Sole ordering authority; async subscribers awaited, sync called inline (`06` §15) |
| T-07-02-02 | Thread-safe ingress | T-07-02-01 | L | P0 | core | N | `call_soon_threadsafe` onto a bounded queue; **the only thread boundary** (ADR-0002) |
| T-07-02-03 | Transport-abstracted ingress contract | T-07-02-02 | M | P0 | core | N | Interface not a concrete call, so a remote publisher is an addition not a redesign (ADR-0007) |
| T-07-02-04 | Gap-free per-capture sequencer | T-07-02-01 | L | P0 | core | N | Assigned at publish; gap-free; makes event loss **provable** (ADR-0017) |
| T-07-02-05 | Split backpressure | T-07-02-01 | L | P0 | core | N | Capture path never drops; UI channels drop-oldest with an `EventsDropped` counter surfaced in the UI |
| T-07-02-06 | Per-subscriber time budget | T-07-02-01 | M | P0 | core | N | Breach raises a warning event; known-slow work goes to an executor |
| T-07-02-07 | `ClockAnomalyDetected` | T-05-02-01 | M | P1 | core | Y | Wall/monotonic divergence beyond threshold records both; covers NTP steps and the macOS/Linux suspend disagreement |
| T-07-02-08 | Ordering and drop adversarial tests | T-07-02-05, T-07-02-04 | L | P0 | tests | N | Saturate a UI channel; assert the `sequence` gap **matches** the `EventsDropped` count (ADR-0022 §5); ordering holds under a threaded publisher storm |

---

# 6. Epic E-3 — Interfaces

## C-08 — REST API (Phase 08)

### WP-08-01 — API foundation

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-08-01-01 | FastAPI app + `/api/v1` router | T-07-02-01 | M | P0 | web | N | Versioned prefix stable per `08` §4 |
| T-08-01-02 | Error response model | T-04-03-01 | M | P0 | web | N | Maps the core error model to HTTP; carries remediation guidance |
| T-08-01-03 | Pagination policy | T-08-01-01 | M | P0 | web | Y | Defaults **and maximum page size** defined (U-02, `08` §10) |
| T-08-01-04 | Filtering and sorting | T-08-01-03 | M | P1 | web | Y | Consistent across collection resources |
| T-08-01-05 | OpenAPI generation | T-08-01-01 | S | P1 | ci | Y | Published as an artifact; drift fails CI |

### WP-08-02 — Resource routes

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-08-02-01 | `/captures` | T-08-01-01, T-06-03-02 | M | P0 | captures | Y | List, get, delete; delete removes the directory (`11` §13) |
| T-08-02-02 | `/studies`, `/series`, `/instances` | T-08-01-01, T-06-03-06 | L | P0 | studies | Y | Projection-backed; per-instance provenance exposed (ADR-0013) |
| T-08-02-03 | `/associations` | T-08-01-01, T-05-01-03 | M | P0 | associations | Y | Pairs exposed as pairs, per-leg timings separate |
| T-08-02-04 | `/events` | T-08-01-01 | M | P0 | captures | Y | Standing resource per `08` §6; queryable by correlation and sequence |
| T-08-02-05 | `/operations/{id}` | T-08-01-01 | M | P0 | core | Y | Reads the job registry (ADR-0023); immediate return + progress (`08` §12) |
| T-08-02-06 | `/settings` | T-08-01-01, T-04-01-03 | M | P0 | settings | Y | Source shown per setting; locked fields locked, not silently discarded |
| T-08-02-07 | `/health` | T-08-01-01, T-04-03-06 | S | P0 | core | Y | Readiness and liveness distinguished |

### WP-08-03 — Access control seams

No authentication exists in v1, so these mitigations are the entire perimeter.
T-08-03-02 in particular: any page the user visits can issue requests to
`localhost:8000`, and DNS rebinding defeats same-origin policy.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-08-03-01 | Read-only mode, single seam | T-08-01-01 | M | P0 | web | N | Server-wide; every mutating route blocked through **one** enforcement point so a later auth ADR need not move it (ADR-0009) |
| T-08-03-02 | Host header allowlist | T-08-01-01 | M | P0 | web | N | `localhost`, `127.0.0.1`, configured names; others rejected |
| T-08-03-03 | Origin / Sec-Fetch-Site checks | T-08-03-02 | M | P0 | web | N | On state-changing requests; **no `Access-Control-Allow-Origin`, ever** |
| T-08-03-04 | Trusted-proxy list | T-08-03-02 | M | P0 | web | Y | Empty by default; forwarded headers otherwise ignored, else audit logs carry attacker-supplied addresses |
| T-08-03-05 | Rate limiting | T-08-01-01 | M | P1 | web | Y | `12` §12; applied to the client-asserted endpoint at minimum |

### WP-08-04 — Client-asserted events and CLI

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-08-04-01 | Client-asserted event endpoint | T-07-01-06, T-08-03-05 | M | P0 | web | N | Dedicated route; `producer` forced to `web-ui`; Viewer category only; rate-limited; payload-validated (ADR-0016) |
| T-08-04-02 | CLI command surface spec | T-08-01-05 | M | P0 | docs | N | Derived from the resource catalog; closes F-07 |
| T-08-04-03 | CLI as API client | T-08-04-02 | L | P0 | cli | N | Live state via `/api/v1`; one lifecycle manager, one bus, one SQLite writer (ADR-0007) |
| T-08-04-04 | Offline one-shot commands | T-08-04-03 | M | P1 | cli | Y | `lumora capture inspect <file>` embedded; scope limited to offline work |

## C-09 — WebSocket (Phase 09)

### WP-09-01 — Dual endpoints

The deciding constraint: one set of Jinja partials must serve both first paint and live
update. If a panel exists twice — a template plus JavaScript — this work package has
failed regardless of whether it functions.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-09-01-01 | `/api/v1/events/stream` JSON | T-07-02-01, T-08-01-01 | L | P0 | web | N | Canonical envelopes; topic subscriptions (`09` §6, §7); for CLI, plugins, integrations |
| T-09-01-02 | `/ws/ui` fragment endpoint | T-09-01-01 | L | P0 | web | N | Server-rendered HTML; a presentation adapter in `web/`, explicitly not part of the API contract (ADR-0019) |
| T-09-01-03 | Shared Jinja partials | T-09-01-02 | L | P0 | web | N | One template per panel, rendered by the HTTP handler initially and the WS adapter on change |
| T-09-01-04 | Out-of-band targeted swaps | T-09-01-03 | M | P0 | web | N | Only changed panels re-render (`15` §16) |
| T-09-01-05 | Subscription by mounted view | T-09-01-02 | M | P0 | web | N | Client declares page and panels; a background tab receives nothing |
| T-09-01-06 | Handshake origin check | T-08-03-03 | S | P0 | web | N | Without it a hostile page subscribes to the live stream and reads PHI as it arrives (ADR-0010) |
| T-09-01-07 | Heartbeat and idle timeout | T-09-01-01 | S | P1 | web | Y | Intervals defined (U-07, `09` §10) |
| T-09-01-08 | Reconnection with subscription resume | T-09-01-05 | M | P1 | web | Y | `09` §11; resumed state matches pre-disconnect |

### WP-09-02 — Coalescing governor

Not optional. ADR-0014 bounded volume but events arrive in bursts; one message per event
destroys the 100 ms budget.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-09-02-01 | Fixed-interval flush | T-09-01-01 | L | P0 | web | N | ~100 ms, configurable; both endpoints fed through it |
| T-09-02-02 | Per-target policies | T-09-02-01 | L | P0 | web | N | Counters aggregate, status rows latest-wins, timeline appends with a cap |
| T-09-02-03 | Drop accounting integration | T-09-02-01, T-07-02-05 | M | P0 | web | N | ADR-0002's drop-oldest lands here; drops provable via sequence gaps |
| T-09-02-04 | Render-once-per-flush sharing | T-09-02-02 | M | P1 | web | Y | One render per distinct view-state shared across clients |
| T-09-02-05 | Burst budget test | T-09-02-02 | M | P0 | tests | N | 5,000-event burst stays within the 100 ms UI budget (`02-alt` §22) |

---

# 7. Epic E-4 — DICOM Observation

## C-10 — DICOM endpoint foundation (Phase 10)

### WP-10-01 — SCP and SCU

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-10-01-01 | SCP listener | T-03-03-01, T-07-02-02 | L | P0 | associations | N | Binds **11112**; port 104 needs root, unacceptable under `12` §3 (ADR-0007) |
| T-10-01-02 | SCU client | T-10-01-01 | L | P0 | associations | N | Association establishment, negotiation, release |
| T-10-01-03 | Bus ingress from association threads | T-10-01-01, T-07-02-03 | L | P0 | associations | N | Publishes through the thread-safe ingress only; no direct bus call from a pynetdicom thread |
| T-10-01-04 | Association audit logging | T-10-01-01, T-06-01-02 | M | P0 | associations | Y | Calling AE and source IP for **every** association (`12` §10, ADR-0009) |
| T-10-01-05 | Optional AE/IP allowlist | T-10-01-04 | M | P1 | associations | Y | Ships available but off; all associations accepted by default — one Probe rejects is one it cannot show you |
| T-10-01-06 | Configurable DICOM bind interface | T-04-01-01 | S | P1 | associations | Y | Independent of the HTTP bind |

### WP-10-02 — Inline proxy relay

T-10-02-05 is the one to get right: a naive parse-and-re-encode normalises non-conformant
data and destroys the evidence the user came for.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-10-02-01 | Relay core | T-10-01-02 | XL | P0 | associations | N | Accept downstream, open upstream, relay both halves (ADR-0003) |
| T-10-02-02 | Pass-through negotiation (default) | T-10-02-01 | L | P0 | associations | N | Open upstream first, mirror accepted presentation contexts downstream; true fidelity |
| T-10-02-03 | Permissive standalone mode | T-10-02-02 | M | P0 | associations | N | Works with no upstream; **always labelled** in UI and manifest — it masks negotiation failures, the exact bug class users hunt |
| T-10-02-04 | Service-agnostic passthrough | T-10-02-01 | L | P0 | associations | N | Unrecognized DIMSE relayed byte-faithfully, recorded structurally, `UnrecognizedDimseObserved`; **never aborted** (ADR-0024) |
| T-10-02-05 | No-repair guarantee | T-10-02-04 | L | P0 | associations | N | Malformed traffic relays unmodified; conformance problems recorded as conditions; test proves bytes are unchanged |
| T-10-02-06 | Per-leg timing attribution | T-10-02-01, T-05-01-03 | L | P0 | associations | N | Downstream leg, Probe hop, upstream leg separately — reporting end-to-end modality↔PACS timing would be a lie (ADR-0003) |
| T-10-02-07 | Destination-AE interception mode | T-10-02-01 | L | P1 | associations | Y | Explicitly configured, separately documented, never automatic (ADR-0024) |

### WP-10-03 — Per-service enrichment

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-10-03-01 | C-ECHO enrichment | T-10-02-04 | S | P0 | associations | Y | Domain events with summary fields |
| T-10-03-02 | C-STORE enrichment | T-10-02-04 | L | P0 | associations | Y | `CStoreReceived`, `DatasetParsed`, `InstancePersisted`; 6–10 domain events per instance (ADR-0014) |
| T-10-03-03 | C-FIND enrichment | T-10-02-04 | M | P0 | associations | Y | Query and response counts |
| T-10-03-04 | C-GET enrichment | T-10-02-04 | M | P0 | associations | Y | Includes SCP/SCU role selection negotiation — itself a classic interop bug, recorded verbatim |
| T-10-03-05 | C-MOVE relay + progress | T-10-02-04 | L | P0 | associations | N | Command and progress responses recorded; sub-operations acknowledged as out-of-band |
| T-10-03-06 | DIMSE summary fields | T-10-03-02 | M | P0 | shared | N | PDU count, bytes, first/last timestamp, max inter-PDU gap on every DIMSE payload — so throughput and stalls are answerable from events alone |

### WP-10-04 — Protocol trace

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-10-04-01 | PDU trace capture | T-10-02-01, T-06-02-04 | L | P0 | captures | N | Type, length, PDV boundaries, presentation context IDs, per-PDU arrival timestamps |
| T-10-04-02 | Trace-to-message keying | T-10-04-01 | M | P0 | captures | N | Keyed to association and message for on-demand drill-down |
| T-10-04-03 | Bus-bypass verification | T-10-04-01 | M | P0 | tests | N | Asserts PDU records never reach the bus; a 500-instance study keeps bus volume at ~5,000 events (ADR-0014) |

## C-11 — Capture engine (Phase 11)

### WP-11-01 — Ring buffer

Ships **enabled** — a considered deviation from `12` §15, because a disabled buffer is a
feature nobody discovers until after they needed it.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-11-01-01 | Bounded ring buffer service | T-10-01-03, T-06-02-02 | XL | P0 | captures | N | Continuous recording; 30 min / 2 GB default, both configurable; retention enforced |
| T-11-01-02 | Events-only switch | T-11-01-01 | M | P0 | captures | N | Documented path for sites that cannot have PHI on disk unprompted |
| T-11-01-03 | Retention state exposure | T-11-01-01 | M | P0 | captures | Y | Expiry visible to the API and UI |
| T-11-01-04 | Buffer capacity test | T-11-01-01 | M | P0 | tests | N | Holds its cap under sustained traffic; expires predictably; no unbounded growth |

### WP-11-02 — Capture sessions and promotion

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-11-02-01 | Explicit capture sessions | T-05-01-04, T-06-02-01 | L | P0 | captures | N | `07` §12 state machine; `CaptureStarted`/`CaptureCompleted`; unbounded |
| T-11-02-02 | Retroactive promotion | T-11-01-01, T-11-02-01 | XL | P0 | captures | N | "Save the last 10 minutes" / "save this association"; copy-and-seal a time slice using digest copies (ADR-0008) |
| T-11-02-03 | Partial-capture marking | T-11-02-02 | L | P0 | captures | N | `partial: true` plus which aggregates are incomplete when a window starts mid-association |
| T-11-02-04 | Fidelity tier recording | T-11-02-01, T-06-02-01 | M | P0 | captures | N | `events` → `protocol` → `wire`; manifest lists which streams are present (ADR-0005, ADR-0014) |
| T-11-02-05 | Clock anchor in manifest | T-11-02-01, T-05-02-01 | S | P0 | captures | Y | One wall+monotonic pair at capture start, so wall time is reconstructible from monotonic |
| T-11-02-06 | Promotion as a background job | T-11-02-02 | M | P1 | captures | Y | Progress on the bus (ADR-0023) |

### WP-11-03 — Crash recovery and durability

Both promises here are unverifiable without their tests, which is why the tests are P0
rather than P1.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-11-03-01 | Torn-line recovery | T-06-02-02 | L | P0 | captures | N | Scan directory, discard torn trailing line, mark `Interrupted`, re-derive index (ADR-0007) |
| T-11-03-02 | `CaptureInterrupted` on shutdown deadline | T-04-03-05, T-11-02-01 | M | P0 | captures | N | Manifest records interruption rather than leaving a silently truncated capture |
| T-11-03-03 | Kill-mid-capture test | T-11-03-01 | L | P0 | tests | N | Process killed during active capture; torn line discarded, capture marked, index rebuilt (ADR-0022 §5) |
| T-11-03-04 | Drain-on-SIGTERM test | T-11-03-02 | M | P0 | tests | N | Last events are persisted, not dropped — `06` §10's durability promise made testable |

### WP-11-04 — Budget ratification

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-11-04-01 | Measure against real traffic | T-11-01-04, T-10-04-03 | L | P0 | tests | N | Event and PDU volumes, buffer fill rate, bus latency measured under representative load |
| T-11-04-02 | Ratify ADR-0030 budgets | T-11-04-01 | M | P0 | docs | N | Provisional thresholds promoted to release gates or revised with evidence; closes F-06 |

---

# 8. Epic E-5 — Investigation

## C-12 — Replay engine (Phase 12)

### WP-12-01 — Replay modes

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-12-01-01 | Event replay | T-07-02-01, T-06-02-02 | XL | P0 | replay | N | Offline into the bus, no network; original or scaled timing; matches `06` §16 exactly |
| T-12-01-02 | Protocol replay | T-12-01-01, T-10-01-02 | XL | P0 | replay | N | Probe as SCU; re-sends captured datasets with original inter-message timing |
| T-12-01-03 | Fidelity gate | T-12-01-02, T-11-02-04 | L | P0 | replay | N | **Refuses** modes the capture cannot support and names the missing stream; degrading silently would let someone conclude "it worked on replay" from a replay that sent nothing |
| T-12-01-04 | Timing reconstruction from monotonic | T-12-01-01, T-05-02-01 | M | P0 | replay | N | Uses `monotonic_ns` deltas, never wall deltas — else an NTP correction replays as a pause (ADR-0017) |
| T-12-01-05 | Refuse unreplayable promoted windows | T-12-01-03, T-11-02-03 | M | P0 | replay | Y | A window whose negotiation was never recorded is refused, not approximated (ADR-0008) |

### WP-12-02 — Replay provenance

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-12-02-01 | Fresh correlation ID linked to original | T-12-01-01 | M | P0 | replay | N | Reusing the original would merge two investigations into one timeline (ADR-0005) |
| T-12-02-02 | `replay_id` / `replay_of_event_id` | T-12-02-01, T-07-01-01 | M | P0 | replay | N | Replayed events distinguishable from production evidence |
| T-12-02-03 | Capture-while-replaying | T-12-02-02 | M | P1 | replay | Y | The normal debugging loop works; provenance preserved in the new capture |

### WP-12-03 — Live-write guardrails

Protocol replay writes real C-STOREs into a real PACS. The failure mode guarded against
is replaying a 900-instance capture into production and creating 900 duplicate objects.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-12-03-01 | Dry-run default | T-12-01-02 | M | P0 | replay | N | Live send requires explicit opt-in |
| T-12-03-02 | Explicit target configuration | T-12-01-02 | M | P0 | replay | N | Target never inherited from the capture |
| T-12-03-03 | C-STORE allowlist enforcement | T-12-03-02 | M | P0 | replay | N | Replay to a non-allowlisted target refused |
| T-12-03-04 | Replay audit logging | T-12-03-01, T-06-01-02 | M | P0 | replay | Y | Every run recorded (`12` §10) |
| T-12-03-05 | Exclusivity | T-12-01-02 | M | P0 | replay | N | One protocol replay at a time, **refused not queued** — concurrent replays interleave associations and make both results uninterpretable |

### WP-12-04 — Job infrastructure

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-12-04-01 | In-memory job registry | T-04-03-03 | L | P0 | core | N | UUIDv7 IDs; asyncio tasks plus executor; no new dependency (ADR-0023) |
| T-12-04-02 | Durable job audit in `app.db` | T-12-04-01, T-06-01-02 | M | P0 | core | N | Type, params, start, end, outcome, checkpoints |
| T-12-04-03 | Startup interruption sweep | T-12-04-02 | M | P0 | core | N | Anything `running` at startup → `Interrupted` with reason; **nothing auto-continues** |
| T-12-04-04 | Progress on the bus | T-12-04-01, T-09-02-01 | M | P0 | core | N | Through the coalescing governor; no second transport (`08` §12) |
| T-12-04-05 | Cooperative cancellation | T-12-04-01 | L | P0 | core | N | Reports how many instances were sent **and confirmed** — a job reporting only `cancelled` is a silent failure where it costs most |
| T-12-04-06 | Per-type concurrency bounds | T-12-04-01 | M | P1 | core | Y | Small worker limits for reports and imports |

### WP-12-05 — Golden fixture regression

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-12-05-01 | Golden `.lpcap` fixtures | T-03-02-04, T-11-02-01 | L | P0 | tests | N | Synthetic; committed; cover the `01` §3 failure catalogue |
| T-12-05-02 | Byte-comparable replay assertion | T-12-05-01, T-12-01-01 | L | P0 | tests | N | Replay yields an identical event stream — the only test shape that catches "we changed the bus and the timeline reordered" (ADR-0022 §2) |

## C-13 — Viewer (Phase 13)

### WP-13-01 — Decode pipeline

Decode duration is a product feature: decoded in the browser it is a property of the
user's laptop and cannot appear in a shared capture or report.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-13-01-01 | Server-side decode | T-06-02-03, T-04-03-07 | XL | P0 | studies | N | pylibjpeg + openjpeg, optional GDCM; to normalized 16-bit grayscale; in an executor, never on the loop |
| T-13-01-02 | Sidecar metadata | T-13-01-01 | M | P0 | studies | N | Dimensions, rescale slope/intercept, suggested window, photometric interpretation |
| T-13-01-03 | `ImageDecoded` with duration | T-13-01-01, T-07-01-02 | M | P0 | studies | N | Duration recorded as evidence, reproducible off the originating machine |
| T-13-01-04 | LRU frame cache | T-13-01-01 | L | P0 | studies | N | Server-side; size a runtime setting (ADR-0020) |
| T-13-01-05 | ±2 prefetch policy | T-13-01-04 | M | P1 | studies | Y | `02-alt` §22 honoured as prefetch, **not** a hard cap (ADR-0015) |
| T-13-01-06 | Decode failure reporting | T-13-01-01, T-04-03-01 | M | P0 | studies | N | Reports *why*; "browser can't show it" and "pixel data is broken" must not be indistinguishable |

### WP-13-02 — Frame endpoints and renderer

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-13-02-01 | Per-instance-per-frame endpoints | T-13-01-01, T-08-01-01 | L | P0 | web | N | Multi-frame and cine **stream** rather than block |
| T-13-02-02 | Cornerstone3D custom image loader | T-13-02-01, T-04-05-01 | L | P0 | web | N | Renderer only, fed by our endpoint; not used as a DICOM parser |
| T-13-02-03 | Client-side W/L, zoom, pan, invert | T-13-02-02 | L | P0 | web | N | Local state, no round trip; W/L drag within 100 ms — the deliberate minimal-JS exception (ADR-0019) |
| T-13-02-04 | Cine playback | T-13-02-03 | M | P1 | web | Y | Client-side over prefetched frames |
| T-13-02-05 | Fullscreen | T-13-02-03 | XS | P2 | web | Y | `15` §7 |

### WP-13-03 — Study browser over projections

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-13-03-01 | Projection rebuild from manifests | T-06-03-03 | L | P0 | studies | N | UID-keyed; rows derived, never authoritative (ADR-0013) |
| T-13-03-02 | Per-instance provenance | T-13-03-01 | M | P0 | studies | N | Which capture each instance came from |
| T-13-03-03 | Partial-study marking | T-13-03-02 | L | P0 | studies | N | "Present in 3 captures", marked `partial`, **never rendered as whole** — silently unioning fragments hides the bug the user came for |
| T-13-03-04 | Duplicate-UID finding | T-13-03-02, T-06-02-03 | L | P0 | studies | N | Two byte sequences under one SOP Instance UID reported with **both** digests and both provenances |
| T-13-03-05 | Ring-buffer retention in browser | T-13-03-01, T-11-01-03 | M | P0 | web | N | Expiring instances show retention state and offer inline promotion |
| T-13-03-06 | Capture-scoped bookmarks | T-13-03-02, T-06-01-02 | M | P1 | studies | Y | Reference capture-scoped instances, not free-floating studies |
| T-13-03-07 | Offline folder import | T-13-03-01, T-11-02-01 | L | P0 | studies | N | Creates a **synthetic capture** at `fidelity: objects`, so protocol replay correctly refuses it; one ingest path, one ownership rule |

### WP-13-04 — Workspace panels

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-13-04-01 | Workspace shell | T-09-01-03 | L | P0 | web | N | Toolbar / Explorer / Viewer / Inspector / bottom dock / status bar; resizable, collapsible (`15` §4) |
| T-13-04-02 | Metadata Inspector | T-13-04-01 | L | P0 | web | Y | Search, copy tag, copy value, JSON export, raw dump, private-tag toggle (`02-alt` §12) |
| T-13-04-03 | Transfer Inspector | T-13-04-01, T-10-02-06 | L | P0 | web | Y | Association ID, presentation context, transfer syntax, receive and decode duration, size, compression, PDU size — per-leg (`02-alt` §13) |
| T-13-04-04 | Event Timeline | T-13-04-01, T-09-01-04 | XL | P0 | web | N | Ordered by `sequence`, never `occurred_at` (ADR-0017); synchronizes with other panels |
| T-13-04-05 | Log console | T-13-04-01 | M | P1 | web | Y | Operational log view, distinct from the event stream (ADR-0014) |
| T-13-04-06 | Live Monitor | T-13-04-01, T-09-01-05 | L | P0 | web | N | Active associations, throughput, `EventsDropped` counter surfaced |
| T-13-04-07 | Dashboard | T-13-04-01 | M | P1 | web | Y | System overview (`14` §16) |
| T-13-04-08 | Search panel | T-13-04-01 | L | P1 | web | Y | Studies, series, instances, events, logs; incremental results (`15` §9) |
| T-13-04-09 | Command palette + keyboard nav | T-13-04-01 | L | P1 | web | N | Mouse not mandatory (`15` §12) |
| T-13-04-10 | `ImageDisplayed` post-back | T-13-02-02, T-08-04-01 | M | P1 | web | Y | Quarantined: `origin: client-asserted`, Viewer category, excluded from analysis, timing and replay fidelity (ADR-0016) |
| T-13-04-11 | Theming | T-13-04-01 | M | P2 | web | Y | Light, dark, system preference (`15` §14) |
| T-13-04-12 | Notifications | T-13-04-01 | M | P1 | web | Y | Critical failures remain visible until acknowledged (`15` §11) |

## C-14 — Analysis (Phase 14)

### WP-14-01 — Ownership decision

First work package in the phase. Without the boundary fixed, the per-leg timing code
grows rules inside it and ADR-0018's separation is lost in practice.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-14-01-01 | ADR-0028 — Analysis ownership | T-10-02-06 | M | P0 | docs | N | Fixes the Transfer Analysis / rule engine boundary; supplies `05`'s missing Analysis owner; closes F-03 |

### WP-14-02 — Diagnostic conditions

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-14-02-01 | Condition ID registry | T-14-01-01 | M | P0 | analysis | N | Stable IDs (`LP-NEG-004` form) with a documented allocation rule (U-04) |
| T-14-02-02 | Condition detection, deterministic | T-14-02-01 | L | P0 | analysis | N | Observed only, no inference; rides the stream as `WarningRaised`/`ErrorRaised` with a `code` field (`06` Appendix A) |
| T-14-02-03 | Condition catalogue documentation | T-14-02-02 | M | P1 | docs | Y | Each ID has meaning and remediation text; citable in a vendor ticket |

### WP-14-03 — Findings engine

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-14-03-01 | Finding model | T-14-01-01 | L | P0 | analysis | N | Rule ID, rule version, confidence, cited sequence numbers, explanation, next steps |
| T-14-03-02 | Coarse confidence levels | T-14-03-01 | S | P0 | analysis | N | `certain`/`likely`/`possible` only; no numeric scores — we have no calibration data and "73%" is invented precision |
| T-14-03-03 | `analysis/` persistence | T-14-03-01, T-06-02-01 | M | P0 | analysis | N | Written inside the capture; **never** to `events.jsonl`; test asserts absence |
| T-14-03-04 | Rule engine | T-14-03-01 | XL | P0 | analysis | N | Declarative where the shape allows, Python where it does not; explanation text alongside the rule |
| T-14-03-05 | Rule-set versioning | T-14-03-04 | M | P0 | analysis | N | Version recorded on every finding and report — so a vanished finding is distinguishable from changed traffic |
| T-14-03-06 | Purity guarantee | T-14-03-04 | L | P0 | analysis | N | Delete `analysis/`, re-run, obtain identical findings; a newer rule set improves findings against unchanged evidence |
| T-14-03-07 | Evidence linking in UI | T-14-03-03, T-13-04-04 | L | P0 | web | N | Every claim links to the events behind it, so a user can check reasoning rather than trust it |
| T-14-03-08 | Exclude client-asserted from inference | T-14-03-04, T-13-04-10 | M | P0 | analysis | N | Never an input to analysis, never contributes timing (ADR-0016) |

### WP-14-04 — Seed rule set

Follows `01` §3 directly — that list is effectively its specification.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-14-04-01 | Rejected association rules | T-14-03-04 | M | P0 | analysis | Y | Result/source/reason triplet → `certain` confidence |
| T-14-04-02 | No acceptable presentation context | T-14-03-04 | M | P0 | analysis | Y | Names the SOP class and what was offered |
| T-14-04-03 | Transfer syntax mismatch | T-14-03-04 | M | P0 | analysis | Y | Offered vs accepted, with remediation |
| T-14-04-04 | Slow C-STORE with per-leg attribution | T-14-03-04, T-10-02-06 | L | P0 | analysis | Y | Attributes delay to a leg rather than asserting end-to-end slowness |
| T-14-04-05 | Incomplete studies / missing instances | T-14-03-04, T-13-03-03 | L | P0 | analysis | Y | The problem being investigated, reported as such |
| T-14-04-06 | Timeouts and retries | T-14-03-04 | M | P0 | analysis | Y | Pattern detection across an association pair |
| T-14-04-07 | Oversized datasets | T-14-03-04 | S | P1 | analysis | Y | Threshold configurable |
| T-14-04-08 | C-MOVE out-of-band finding | T-14-03-04, T-10-03-05 | M | P0 | analysis | Y | States that sub-operation data flows out-of-band; concrete remediation — point the destination AE at Probe, or use C-GET (ADR-0024) |

## C-15 — Reports and handover (Phase 15)

### WP-15-01 — Report generation

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-15-01-01 | Jinja report templates | T-14-03-01 | L | P0 | reports | N | HTML and Markdown (`04` §11) |
| T-15-01-02 | PDF decision and path | T-15-01-01 | M | P1 | reports | N | U-08 resolved: either a named dependency with rationale, or print-to-PDF documented as the answer |
| T-15-01-03 | Report content assembly | T-15-01-01, T-14-03-05 | L | P0 | reports | N | Conditions, findings, timings, provenance, rule-set version |
| T-15-01-04 | Generation as a background job | T-15-01-03, T-12-04-01 | M | P0 | reports | Y | Progress on the bus; cheap to redo, never resumed |
| T-15-01-05 | `ReportGenerated` event | T-15-01-03 | XS | P1 | reports | Y | Catalog updated |

### WP-15-02 — Redaction

Naming discipline is the control here: the code cannot verify burned-in annotation, so the
product must not claim it did.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-15-02-01 | Tag-level redaction profile | T-06-02-03 | L | P0 | reports | N | Configurable; applied to a copy |
| T-15-02-02 | Consistent UID remapping | T-15-02-01 | L | P0 | reports | N | Hierarchy survives redaction — the browser is UID-keyed (ADR-0013) |
| T-15-02-03 | Output as a new capture | T-15-02-01, T-11-02-01 | L | P0 | captures | N | New ID; manifest records source capture ID and profile; original untouched (ADR-0004) |
| T-15-02-04 | Unverifiable-content warnings | T-15-02-01 | L | P0 | reports | N | `BurnedInAnnotation`, Secondary Capture / US / screenshot SOP classes, unrecognized private tags, free-text fields all flagged |
| T-15-02-05 | Terminology audit | T-15-02-04 | S | P0 | docs | N | "Redact" only; no UI string or document says "anonymize" or "de-identified"; no PS3.15 conformance claim (ADR-0026) |

### WP-15-03 — Handover export

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-15-03-01 | Object-dropping export as default | T-11-02-04, T-06-02-05 | L | P0 | captures | N | `fidelity: events` — events, traces, whitelisted metadata, **no pixel data** |
| T-15-03-02 | Pixel-bearing export as opt-in | T-15-03-01 | M | P0 | captures | N | Deliberate action, clearly labelled |
| T-15-03-03 | Handover documentation | T-15-03-01 | M | P1 | docs | Y | The `01` §8 vendor workflow end to end |

---

# 9. Epic E-6 — Extensibility and Operations

## C-16 — Plugin SDK (Phase 16)

### WP-16-01 — Hook surface

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-16-01-01 | pluggy hook specifications | T-14-03-04 | L | P0 | plugins | N | Event subscription, analyzers, report contributions, commands, settings (`10` §5) |
| T-16-01-02 | Contracts-only exposure | T-16-01-01 | M | P0 | plugins | N | Plugins see `contracts.py` DTOs; leaking an aggregate makes every refactor an ecosystem break (ADR-0006) |
| T-16-01-03 | Manifest schema | T-16-01-01 | M | P0 | plugins | N | Capabilities declared for **disclosure, not enforcement** |
| T-16-01-04 | SDK versioning + deprecation window | T-16-01-01 | M | P0 | docs | N | Scheme documented (U-09, `10` §12) |
| T-16-01-05 | SDK documentation + example plugin | T-16-01-02 | L | P1 | docs | Y | `10` §14; example builds against public surfaces only |

### WP-16-02 — Loader and containment

What is deliverable toward `10` §4 and `12` §11, stated honestly: we can measure and
disable, we cannot interrupt.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-16-02-01 | Plugin discovery and load | T-16-01-03 | L | P0 | plugins | N | From `LUMORA_DATA_DIR/plugins/`; ships disabled |
| T-16-02-02 | Load-time structural validation | T-16-02-01 | M | P0 | plugins | N | Manifest schema, SDK range, entry points, declared hooks exist — `12` §11's "validate before activation" honestly scoped |
| T-16-02-03 | SDK compatibility gate | T-16-02-02 | M | P0 | plugins | N | Incompatible major refused at load, not crashing mid-hook |
| T-16-02-04 | Exception containment per hook | T-16-02-01 | L | P0 | plugins | N | Never propagates into core; `ErrorRaised` with plugin ID; auto-disable after repeated failure |
| T-16-02-05 | Per-hook time budget | T-16-02-04, T-07-02-06 | M | P0 | plugins | N | Warning then auto-disable; documented that an infinite loop still stalls the loop |
| T-16-02-06 | Restart-scoped enable/disable | T-16-02-01 | M | P0 | plugins | N | Enabling runs code, so it is restart-scoped |
| T-16-02-07 | No API installation | T-16-02-01, T-08-01-01 | M | P0 | web | N | List, enable, disable, inspect only. An install endpoint on unauthenticated loopback is arbitrary code execution reachable by any local process (ADR-0021) |
| T-16-02-08 | CLI install command | T-16-02-07 | M | P0 | cli | N | Filesystem placement plus a deliberate command; restart required |
| T-16-02-09 | Trust disclosure in UI | T-16-02-06 | S | P0 | web | Y | States plainly that an enabled plugin can do anything the process can; claims **no** capability enforcement |

### WP-16-03 — Seed rules re-homed

The cheapest way to discover the extension points are wrong is to build the first-party
analyzers on them.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-16-03-01 | Port seed rules to bundled plugins | T-16-01-02, T-14-04-08 | XL | P0 | plugins | N | All seed rules run on the **public** SDK with no privileged access |
| T-16-03-02 | Extension point gap report | T-16-03-01 | M | P0 | docs | N | Anything the port could not express is recorded and the SDK fixed, not worked around |

## C-17 — Observability (Phase 17)

### WP-17-01 — Metrics from events

One counting path, so `14` §6's metrics cannot disagree with `14` §4's events.

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-17-01-01 | Event-derived metric registry | T-07-02-01 | L | P0 | core | N | In-process; derived from the stream, not separately instrumented (ADR-0014) |
| T-17-01-02 | Metric exposure on API | T-17-01-01, T-08-01-01 | M | P0 | web | Y | `14` §6 categories |
| T-17-01-03 | Metrics dashboard | T-17-01-02, T-13-04-07 | M | P1 | web | Y | `14` §16 |
| T-17-01-04 | Metric/event agreement test | T-17-01-01 | M | P0 | tests | N | A metric and its underlying event count agree by construction |

### WP-17-02 — Health and diagnostics

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-17-02-01 | Per-service health reporting | T-04-03-06 | M | P0 | core | Y | Every `Service` reports; aggregated (`14` §9) |
| T-17-02-02 | Per-plugin health and version | T-16-02-05 | M | P0 | plugins | Y | "The tool got slow" resolves to a named plugin (`14` §15) |
| T-17-02-03 | Operational logging discipline | T-04-03-02 | M | P0 | core | N | `app.log` carries application logging, **not** a mirror of domain events (ADR-0014) |
| T-17-02-04 | Alerting thresholds | T-17-01-01 | M | P1 | core | Y | Configurable (`14` §11) |
| T-17-02-05 | Incident investigation support | T-17-01-01, T-13-04-04 | M | P1 | web | Y | Timeline reconstruction, evidence preservation (`14` §17) |
| T-17-02-06 | Audit log coverage | T-06-01-02 | M | P0 | core | N | Every `12` §10 category: associations, config changes, replays, exports, deletions |

---

# 10. Epic E-7 — Release Readiness

## C-18 — Hardening (Phase 18)

### WP-18-01 — Performance

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-18-01-01 | Startup time | T-11-04-02 | M | P1 | core | Y | Against the ratified budget |
| T-18-01-02 | Large study handling | T-11-04-02, T-13-03-01 | L | P0 | studies | N | Thousands of instances — the Enhanced MR case named in `01` §3 |
| T-18-01-03 | Event throughput under load | T-11-04-02 | L | P0 | core | N | Bus does not stall; drops accounted |
| T-18-01-04 | Memory profile | T-18-01-02 | M | P1 | core | Y | Bounded under sustained capture |
| T-18-01-05 | Replay performance | T-12-01-01 | M | P1 | replay | Y | Timing fidelity maintained under load |
| T-18-01-06 | Concurrent client load | T-09-02-04 | M | P1 | web | Y | Desktop-scale counts (`15` §15) |
| T-18-01-07 | Virtualized tables | T-13-04-08 | M | P1 | web | Y | Large datasets remain responsive (`02-alt` §22) |

### WP-18-02 — Security and accessibility

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-18-02-01 | Input validation review | T-08-01-02 | L | P0 | web | N | Every boundary; `12` §8 |
| T-18-02-02 | Path containment re-verification | T-04-02-04 | M | P0 | core | N | Re-tested against every path-accepting route added since Phase 04 |
| T-18-02-03 | Dependency vulnerability review | T-03-01-05 | M | P0 | ci | Y | Clean, or exceptions recorded with rationale |
| T-18-02-04 | Secret handling review | T-04-03-02 | M | P1 | core | Y | No secrets in logs, events, or captures (`12` §6) |
| T-18-02-05 | Keyboard-only operation | T-13-04-09 | L | P0 | web | N | Primary workflows complete without a mouse (`15` §12) |
| T-18-02-06 | Contrast and scalable typography | T-13-04-11 | M | P1 | web | Y | `15` §13; high-contrast theme available |
| T-18-02-07 | Screen reader pass | T-18-02-05 | M | P2 | web | Y | Where practical (`15` §13); limitations documented honestly |

### WP-18-03 — Documentation

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-18-03-01 | Glossary reconciliation | T-16-03-01 | M | P0 | docs | N | Adds ring buffer, promotion, fidelity tier, condition, finding, association pair, `.lpcap`; corrects Study, Replay, Event Store; closes F-05 |
| T-18-03-02 | Deployment topology guide | T-15-03-03 | L | P0 | docs | N | Inline proxy, destination-AE interception, standalone; reverse proxy as the security boundary |
| T-18-03-03 | Operator guide | T-18-03-02 | L | P0 | docs | N | Exposure acknowledgment, network-filesystem limits, backup targeting `app.db`, index rebuild as a recovery step |
| T-18-03-04 | Troubleshooting guide | T-18-03-03 | M | P1 | docs | Y | Keyed to condition IDs |
| T-18-03-05 | User documentation | T-13-04-01 | L | P1 | docs | Y | Workflow-oriented, per persona |

## C-19 — Packaging (Phase 19)

### WP-19-01 — Distribution

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-19-01-01 | Wheel and sdist with assets | T-04-05-04 | M | P0 | root | N | Committed artifacts included (ADR-0025) |
| T-19-01-02 | No-Node install verification | T-19-01-01 | M | P0 | tests | N | `uv pip install` then run, on a machine with **no Node and no network** |
| T-19-01-03 | Docker image | T-19-01-01 | L | P0 | docker | N | Exposure flag set, non-root user, one volume, proxy boundary documented (ADR-0010, ADR-0011) |
| T-19-01-04 | Volume ownership contract | T-19-01-03 | M | P0 | docker | N | Non-root ownership is part of the image contract |
| T-19-01-05 | No-outbound-request verification | T-19-01-02 | M | P0 | tests | N | No request on any page load — `02-alt` §21 promises it and ADR-0009 rests on it |
| T-19-01-06 | Upgrade and migration notes | T-06-01-04 | M | P1 | docs | Y | `app.db` migrated, `index.db` rebuilt |
| T-19-01-07 | Newer-data-directory refusal test | T-04-02-06 | S | P1 | tests | Y | Refused, not mangled |

## C-20 — Release (Phase 20)

### WP-20-01 — Interoperability

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-20-01-01 | DCMTK suite | T-03-02-03, T-10-02-01 | L | P0 | tests | Y | Positive and negative scenarios (`13` §10) |
| T-20-01-02 | dcm4che suite | T-03-02-03 | L | P0 | tests | Y | As above |
| T-20-01-03 | Orthanc suite | T-03-02-03 | L | P0 | tests | Y | As above |
| T-20-01-04 | Transfer syntax matrix | T-20-01-01 | L | P0 | tests | N | Including the exotic syntaxes that are the product's reason to exist |
| T-20-01-05 | Interop results publication | T-20-01-04 | M | P0 | docs | N | Published; failures triaged, not omitted |

### WP-20-02 — Acceptance and ship

| ID | Task | Deps | Cx | P | Module | ∥ | Acceptance |
|----|------|------|----|---|--------|---|------------|
| T-20-02-01 | PRD acceptance validation | T-20-01-05 | L | P0 | tests | N | Every `02-alt` §26 item demonstrated |
| T-20-02-02 | Definition-of-Done audit | T-20-02-01 | L | P0 | docs | N | `00` §11 satisfied per shipped feature |
| T-20-02-03 | Known-limitations statement | T-20-02-02 | M | P0 | docs | N | C-MOVE sub-operations, no authentication, no PS3.15 conformance, plugin trust model — documented plainly |
| T-20-02-04 | Release notes and changelog | T-20-02-02 | M | P0 | docs | Y | Versioning scheme stated |
| T-20-02-05 | GA sign-off | T-20-02-03 | S | P0 | docs | N | All milestone exit criteria met (`04-milestones.md`) |

---

# 11. Coverage and traceability

## 11.1 Task counts by phase

| Phase | WPs | Tasks | Phase | WPs | Tasks |
|-------|-----|-------|-------|-----|-------|
| 01 | 1 | 5 | 11 | 4 | 16 |
| 02 | 2 | 6 | 12 | 5 | 21 |
| 03 | 3 | 11 | 13 | 4 | 30 |
| 04 | 5 | 26 | 14 | 4 | 20 |
| 05 | 2 | 11 | 15 | 3 | 13 |
| 06 | 3 | 18 | 16 | 3 | 16 |
| 07 | 2 | 15 | 17 | 2 | 10 |
| 08 | 4 | 21 | 18 | 3 | 19 |
| 09 | 2 | 13 | 19 | 1 | 7 |
| 10 | 4 | 22 | 20 | 2 | 10 |

**Totals: 7 epics · 20 capabilities · 59 work packages · 310 tasks.**

Phases 13 and 10 carry the largest task counts, which is where the risk concentrates: the
viewer spans four subsystems, and the DICOM edge is the only phase depending on behaviour
we do not control.

## 11.2 Findings traceability

| Finding | Closing task(s) |
|---------|-----------------|
| F-01 | T-01-01-02 |
| F-02 | T-01-01-04 |
| F-03 | T-14-01-01 |
| F-04 | T-07-01-05 |
| F-05 | T-18-03-01 |
| F-06 | T-03-03-02 (provisional), T-11-04-02 (final) |
| F-07 | T-08-04-02 |
| F-08 | T-06-03-06 |
| U-01 | T-06-01-01, T-06-01-02 |
| U-02 | T-08-01-03 |
| U-03 | T-04-03-01 |
| U-04 | T-14-02-01 |
| U-05 | T-06-03-05 |
| U-06 | T-04-03-06 |
| U-07 | T-09-01-07 |
| U-08 | T-15-01-02 |
| U-09 | T-16-01-04 |
| U-10 | T-06-02-06 |

## 11.3 Deferred work — not scheduled

Per `../adr/README.md`, each needs its own ADR first. Listed so no task above is mistaken
for covering them: pcap import · byte-exact / mock-peer replay · remote collectors ·
multi-user auth and RBAC · plugin installation over the API · config profiles · DIMSE-N
enrichment · Prometheus exposition · PS3.15 de-identification profile.

---

# 12. References

`00-architecture-review-findings.md` · `02-phase-plan.md` · `03-dependency-graph.md` ·
`06-deliverables.md` · `07-definition-of-done.md` · `08-implementation-order.md` ·
`../adr/` (0001–0026) · all 21 baseline documents.
