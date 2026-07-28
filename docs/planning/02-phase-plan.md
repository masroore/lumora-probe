# 02 — Phase Plan

> **Project:** Lumora Probe
>
> **Document:** Phase Plan
>
> **Status:** Planning Baseline
>
> **Audience:** Architects, Engineering, QA, Product, Claude Code, Codex

---

# 1. Purpose

This document defines the 20 implementation phases for Lumora Probe, their objectives,
entry and exit criteria, and the ADR obligations each discharges.

It is the **canonical definition of phase numbering** for the project. Seven ADRs cite
phase numbers that no baseline document defined (F-02); §3 reconciles them.

---

# 2. Phase model

## 2.1 What a phase is

A phase is a **capability boundary**, not a time box. It completes when its exit criteria
are met, and no earlier.

Phases are numbered `01`–`20`. Work packages carry their phase number
(`WP-07-03` = Phase 07, third work package), so a task ID states its phase.

## 2.2 Sequencing rules

1. A phase MAY start when its entry criteria hold — not when the previous phase ends.
   Several phases overlap legitimately; `03-dependency-graph.md` gives the true graph.
2. A phase MUST NOT be declared complete with a failing quality gate
   (`07-definition-of-done.md`).
3. Phases 01–07 are **foundational and strictly ordered** in effect: each supplies a
   primitive the next assumes.
4. Phases 08–17 admit substantial parallelism.
5. Phases 18–20 are convergent — they gate on everything before them.

## 2.3 Two conventions worth stating once

**Spikes resolve empirical questions before the design that depends on them.** Three
are scheduled: pynetdicom threading (Phase 03, feeding Phase 10), Cornerstone3D
bundling (Phase 04), SQLite-under-concurrency (Phase 06).

**Every phase ships tests with its code.** There is no test phase. ADR-0022 weights the
suite to component level, so a phase's tests are part of its deliverable, and Phase 18
hardens rather than first-tests.

---

# 3. Reconciling the ADR phase citations (closes F-02)

## 3.1 The problem

Seven ADRs commit work to numbered phases. No baseline document defines phases by those
numbers: `16` §5–§9 gives five named phases, `02-alt` §24 gives eight. Neither matches
the citations.

## 3.2 The resolution

This document adopts the 20-phase structure the build brief illustrates, because five of
the seven ADR citations land on it exactly:

| ADR | Cites | This plan's phase | Match |
|-----|-------|-------------------|-------|
| ADR-0001 | Phase 01 | 01 Architecture Review | ✓ exact |
| ADR-0025 | Phase 04 | 04 Core Infrastructure | ✓ exact |
| ADR-0022 | Phase 05 | 05 Domain Model | ✓ exact |
| ADR-0007 | Phase 05 (rejected alt.) | 05 Domain Model | ✓ exact |
| ADR-0002 | Phase 11 | 11 Capture Engine | ✓ exact |
| ADR-0007 | Phase 12 (crash recovery) | 12 Replay Engine | ⚠ drift → **Phase 11** |
| ADR-0005 | Phase 13 (replay modes) | 13 Viewer | ⚠ drift → **Phase 12** |
| ADR-0021 | Phase 17 (seed rules as plugins) | 17 Observability | ⚠ drift → **Phase 16** |

Three citations sit one position off their evident subject. The pattern is consistent
with the ADR authors working from a list where Replay preceded Viewer and Plugin SDK sat
at 17.

**Rule adopted:** where an ADR's phase number and its subject matter disagree, **the
subject matter wins**. The three drifted citations are read as:

- ADR-0007's crash-recovery path → **Phase 11** (with the capture writer that creates the
  torn-line condition)
- ADR-0005's two replay modes → **Phase 12** (the Replay Engine phase)
- ADR-0021's seed rule set on the public SDK → **Phase 16** (the Plugin SDK phase)

No ADR is rewritten; `17` §12 forbids that. This mapping is the record.

---

# 4. Phase summary

| # | Phase | Primary output | Milestone reached |
|---|-------|----------------|-------------------|
| 01 | Architecture Review | Findings, gap register, 4 new ADRs | M1 Architecture Frozen |
| 02 | Repository Foundation | Package skeleton, import-linter contracts | M2 Repository Ready |
| 03 | Development Infrastructure | CI, quality gates, test harness, 1 spike | M3 Pipeline Green |
| 04 | Core Infrastructure | Config, errors, logging, IDs, clock, assets | — |
| 05 | Domain Model | Value objects, aggregates, `Clock`/`IdGenerator` | M4 Core Complete |
| 06 | Storage | Schemas, repositories, capture format | M5 Storage Complete |
| 07 | Event System | Bus, envelope, sequencer, catalog | M6 Event Backbone Complete |
| 08 | REST API | `/api/v1`, error model, CLI surface | — |
| 09 | WebSocket | Dual endpoints, coalescing governor | M7 API Complete |
| 10 | DICOM Networking | SCP/SCU, relay, association pairs | M8 Traffic Observable |
| 11 | Capture Engine | Ring buffer, writer, promotion, recovery | M9 Capture Operational |
| 12 | Replay Engine | Event replay, protocol replay, guardrails | M10 Replay Operational |
| 13 | Viewer | Decode pipeline, frame endpoints, renderer | M11 Viewer Operational |
| 14 | Analysis | Conditions, findings, rule engine | — |
| 15 | Reports | Generation, export, redaction, handover | M12 Beta Ready |
| 16 | Plugin SDK | Hooks, loader, seed rules as plugins | — |
| 17 | Observability | Metrics, health, dashboards, diagnostics | M13 Release Candidate |
| 18 | Production Hardening | Performance, security, docs, glossary | — |
| 19 | Packaging | Wheel, sdist, Docker, install paths | — |
| 20 | Release | Interop matrix, acceptance, GA | M14 Production Ready |

---

# 5. Phase detail

Each phase states its objective, entry and exit criteria, the ADRs it discharges, and
the findings from `00-architecture-review-findings.md` it closes.

## Phase 01 — Architecture Review

**Objective.** Close the four gaps this review found that need decisions, and freeze the
architecture. Per ADR-0001 this phase delivers a review and gap register, not a
stop-the-line report.

**Entry.** Baseline and ADR layer exist. (Met.)

**Work.** `00-architecture-review-findings.md` (delivered) · ADR-0027 authoritative PRD
(F-01) · ADR-0030 non-functional budgets (F-06, drafted here, ratified Phase 11) ·
ADR-0028 and ADR-0029 scheduled to their owning phases, not written now.

**Exit.**
- Findings document accepted.
- ADR-0027 accepted — the PRD ambiguity is resolved before any requirement is traced.
- Gap register carried into the WBS with owning phases.
- No open finding rated High without an owner.

**Discharges.** ADR-0001. **Closes.** F-01, F-02.

## Phase 02 — Repository Foundation

**Objective.** An empty but architecturally correct repository: the slice structure from
ADR-0012 with boundaries already machine-enforced.

**Entry.** Phase 01 exit.

**Work.** `pyproject.toml` (uv + Hatchling, `04` §3) · the nine slices of ADR-0012 with
`domain.py` / `service.py` / `repository.py` / `api.py` / `contracts.py` stubs ·
import-linter contracts, all six · directory layout per `18` §4 · licence, README,
`CONTRIBUTING`.

**Exit.**
- `import-linter` runs and passes on the empty skeleton.
- A deliberately illegal import (`domain.py` importing FastAPI) is proven to fail the
  check. An unproven guard is not a guard.
- `uv sync` succeeds from a clean checkout.

**Discharges.** ADR-0012.

## Phase 03 — Development Infrastructure

**Objective.** The quality gate that every later phase relies on, plus the one spike that
must land before DICOM design.

**Entry.** Phase 02 exit.

**Work.** CI pipeline with `13` §15's gates (format, lint, static analysis, tests,
security scan, coverage) · pytest with `pytest-asyncio` and marker taxonomy (ADR-0022)
· synthetic DICOM fixture generator — script, never real data, not even de-identified
(ADR-0022 §3) · **Spike: pynetdicom threading model**, resolving ADR-0002's open
empirical question ahead of Phase 10 · provisional non-functional budgets from
ADR-0014's figures (F-06) · scheduled (non-gating) interop job skeleton (ADR-0022 §4).

**Exit.**
- CI green on an empty repository, every gate active rather than stubbed.
- Fixture generator produces a reviewable synthetic study.
- Threading spike answers: which thread runs `EVT_C_STORE`, what blocks, what the
  ingress contract must therefore accept. Written up as an ADR amendment or confirmed.
- Budgets recorded as provisional, with the Phase 11 ratification task created.

**Discharges.** ADR-0022 §4, §6. **Closes.** F-06 (provisionally).

## Phase 04 — Core Infrastructure

**Objective.** `core/` and `shared/` primitives — everything the slices import and
nothing that imports a slice.

**Entry.** Phase 03 exit.

**Work.** Two-tier configuration with provenance tagging (ADR-0020) · `LUMORA_DATA_DIR`
resolution, path containment assertions, network-filesystem refusal, version marker
(ADR-0011) · structured error model with remediation guidance and a code namespace
(U-03, `03` §12) · structlog with correlation IDs (ADR-0014) · `Service` protocol,
lifecycle manager, draining shutdown (ADR-0007) · health readiness/liveness split
(U-06) · **Spike: Cornerstone3D bundling** and the asset pipeline (ADR-0025).

**Exit.**
- Startup refuses a non-loopback bind without acknowledgment, and explains why
  (ADR-0010).
- A malformed config key aborts startup naming the key **and its source** (ADR-0020).
- Path traversal attempt (`capture_id` of `../../etc`) is rejected by test.
- Asset build produces committed artifacts; CI fails on stale assets.
- Lifecycle manager starts and stops heterogeneous services in reverse order.

**Discharges.** ADR-0007 (lifecycle), ADR-0010, ADR-0011, ADR-0020, ADR-0025.
**Closes.** U-03, U-06.

## Phase 05 — Domain Model

**Objective.** The plain-Python domain, and the two injected primitives that make every
later test deterministic.

**Entry.** Phase 04 exit.

**Work.** Frozen dataclass value objects with `__post_init__` invariants (ADR-0006) ·
aggregates: Association, AssociationPair, Capture, Replay, Report (ADR-0003, ADR-0008)
· lifecycle state machines per `07` §12 · **`Clock` and `IdGenerator` as core protocols,
injected, never called directly** (ADR-0022 §1) · deterministic doubles: controllable
wall clock, manually advanced monotonic counter, seeded UUIDv7 sequence · import-linter
contract banning `time.` and `uuid.` outside `core/`.

**Exit.**
- No module outside `core/` imports `time` or `uuid`, enforced not remembered.
- Both halves of `Clock` are independently freezable — ADR-0017's split is meaningless
  otherwise.
- Aggregate invariants raise domain errors, not `ValidationError` (ADR-0006).
- Domain modules import no framework; verified by contract.

**Discharges.** ADR-0006, ADR-0022 §1.

## Phase 06 — Storage

**Objective.** The physical layer the baseline explicitly declined to specify (`11` §6),
and the capture format that is the product's core artifact.

**Entry.** Phase 05 exit.

**Work.** `index.db` and `app.db` schemas, physically split (ADR-0023) · SQLite WAL,
`busy_timeout`, single writer · repositories with hand-written row↔domain mapping
(ADR-0006) · capture directory format: `manifest.json`, `events.jsonl`, `pdus.jsonl`,
content-addressed `objects/` (ADR-0004) · `.lpcap` pack/unpack and format version (U-10)
· index rebuild from capture directories · additional read-only capture roots (ADR-0011)
· retention semantics (U-05) · **ADR-0029: cascade semantics** for cross-capture
projections (F-08) · **Spike: SQLite under concurrent readers with one writer**.

**Exit.**
- Index is provably rebuildable: delete `index.db`, rebuild, byte-compare the
  projection.
- Dropping a `.lpcap` into the captures folder makes it appear.
- Object digests verify; a tampered object is detected.
- `index.db` on a simulated network path is refused, not corrupted.
- ADR-0029 accepted; cascade behaviour tested for the three-capture study case.

**Discharges.** ADR-0004, ADR-0011 (roots), ADR-0023 (DB split). **Closes.** U-01, U-05,
U-10, F-08.

## Phase 07 — Event System

**Objective.** The event bus — "the heart of Lumora Probe" (`03` §5) — with ordering as a
property of one sequencer.

**Entry.** Phase 06 exit.

**Work.** Loop-owned bus, thread-safe ingress via `call_soon_threadsafe` onto a bounded
queue (ADR-0002) · transport-abstracted ingress contract (ADR-0007) · **the current
envelope**: `06` §6 plus `origin` (ADR-0016), `monotonic_ns` and `sequence` (ADR-0017),
`replay_id` / `replay_of_event_id` (ADR-0005) · payload-model registry keyed by
`(event_name, event_version)` (ADR-0006) · unknown-field preservation, raw bytes kept on
the capture-write path (`06` §3, §16) · gap-free per-capture sequencer (ADR-0017) ·
split backpressure: capture never drops, UI channels drop-oldest with `EventsDropped`
(ADR-0002) · per-subscriber time budget · `ClockAnomalyDetected` (ADR-0017) ·
**generated versioned event catalog** (F-04).

**Exit.**
- Sequence is gap-free under load; a saturated UI channel produces a sequence gap that
  **matches** the `EventsDropped` count (ADR-0022 §5).
- `origin` absent is a validation error, not an assumed-trusted event (ADR-0016).
- An event with unknown future fields round-trips without loss.
- Catalog is generated from code, versioned, and published as an artifact.
- Ordering within an aggregate holds across a threaded publisher storm.

**Discharges.** ADR-0002, ADR-0016, ADR-0017. **Closes.** F-04.

## Phase 08 — REST API

**Objective.** `/api/v1` as the canonical surface — the UI, CLI and plugins all consume
it (`08` §2, `03` §10).

**Entry.** Phase 07 exit.

**Work.** Resource routes per `08` §6 · consistent error model over Phase 04's code
namespace · pagination defaults and maximum page size (U-02) · long-running operations:
immediate return, operation ID, progress endpoint (`08` §12, ADR-0023) · read-only mode
at a **single** enforcement seam (ADR-0009) · Host allowlist, `Origin` /
`Sec-Fetch-Site` checks, no CORS header ever, trusted-proxy list empty by default
(ADR-0010) · client-asserted event endpoint: dedicated, `producer` forced, Viewer
category only, rate-limited (ADR-0016) · **CLI command surface** derived from the
resource catalog plus the two offline commands (F-07, ADR-0007) · OpenAPI generation.

**Exit.**
- Read-only mode blocks every mutating route through one seam, proven by test.
- A request with a foreign `Host` is rejected; a cross-origin state change is rejected.
- Client-asserted events cannot be written outside the Viewer category.
- CLI talks to a running server for live state and embeds only for offline work.
- OpenAPI published as an artifact.

**Discharges.** ADR-0009 (read-only seam), ADR-0010 (HTTP mitigations), ADR-0016
(endpoint). **Closes.** U-02, F-07.

## Phase 09 — WebSocket

**Objective.** Live updates on both endpoints without a client-side rendering layer.

**Entry.** Phase 08 exit.

**Work.** `/api/v1/events/stream` — canonical JSON envelopes, topic subscriptions (`09`
§6, §7) · `/ws/ui` — server-rendered HTML fragments, a presentation adapter in `web/`
(ADR-0019) · **coalescing governor, not optional**: ~100 ms flush, per-target policies
(counters aggregate, status latest-wins, timeline appends with a cap) · out-of-band
targeted swaps (`15` §16) · subscriptions by mounted view, not topic · heartbeat interval
and idle timeout (U-07) · `Origin` check on the handshake (ADR-0010) · reconnection with
subscription resume (`09` §11).

**Exit.**
- One set of Jinja partials serves both first paint and live update. If a panel exists
  twice, this phase has failed its purpose.
- A burst of 5,000 events does not exceed the 100 ms UI budget (`02-alt` §22).
- WebSocket handshake from a hostile origin is refused — without this, a page can read
  PHI as it arrives.
- A background view receives no fragments.

**Discharges.** ADR-0019. **Closes.** U-07.

## Phase 10 — DICOM Networking

**Objective.** Observe real traffic. The riskiest phase, and the first with external
dependencies on behaviour we do not control.

**Entry.** Phase 09 exit **and** Phase 03's threading spike resolved.

**Work.** SCP and SCU foundation on pynetdicom, binding **11112** not 104 (ADR-0007) ·
inline proxy relay (ADR-0003) · pass-through negotiation (default) and permissive
standalone mode, always labelled · association pairs as first-class, per-leg timing
attribution · **service-agnostic relay**: unrecognized DIMSE passed through
byte-faithfully and recorded, `UnrecognizedDimseObserved` (ADR-0024) · per-service
enrichment for C-ECHO, C-STORE, C-FIND, C-GET · C-MOVE relayed with progress responses
plus the explanatory finding · destination-AE interception as a labelled mode ·
`pdus.jsonl` protocol trace writer, off the bus (ADR-0014) · DIMSE summary fields on
domain events · all associations accepted by default, each audit-logged with calling AE
and source IP; optional allowlist (ADR-0009).

**Exit.**
- C-STORE observed end to end against real pynetdicom on loopback.
- Malformed traffic relays **without repair** — a naive parse-and-re-encode would hide
  the defect the user came for (ADR-0024).
- Unrecognized command passes through and is recorded, never aborted.
- Per-leg timings attributed separately for downstream, Probe hop and upstream.
- Domain event volume per instance matches ADR-0014's bound; the bus does not stall.

**Discharges.** ADR-0003, ADR-0014 (trace tier), ADR-0024.

## Phase 11 — Capture Engine

**Objective.** Evidence that survives a crash and can be handed to a vendor.

**Entry.** Phase 10 exit.

**Work.** Always-on bounded ring buffer, **enabled by default**, 30 min / 2 GB
configurable, with the documented events-only switch (ADR-0008) · explicit capture
sessions with `07` §12's state machine · retroactive promotion of a window to a permanent
capture · `partial: true` and incomplete-aggregate marking on mid-association truncation
· manifest: identity, provenance, fidelity, digests, clock anchor, client-asserted count
· fidelity tiers `events` → `protocol` → `wire` (ADR-0005, ADR-0014) · **crash recovery**:
torn trailing line discarded, capture marked `Interrupted`, index re-derived (ADR-0007,
per §3.2 mapping) · draining shutdown with `CaptureInterrupted` on deadline · **ratify
non-functional budgets against real traffic** (F-06).

**Exit.**
- Kill mid-capture: torn line discarded, capture marks `Interrupted`, index rebuilds
  (ADR-0022 §5). Tested, not asserted.
- Promotion of a mid-association window is marked partial and names what is incomplete.
- Ring buffer holds its cap under sustained traffic and expires predictably.
- Budgets ratified and promoted from provisional to release gates.

**Discharges.** ADR-0005 (capture side), ADR-0007 (recovery), ADR-0008.
**Closes.** F-06 (final).

## Phase 12 — Replay Engine

**Objective.** Two replay modes, and guardrails proportionate to the fact that one of
them writes into a live PACS.

**Entry.** Phase 11 exit.

**Work.** **Event replay** — offline into the bus, no network, original or scaled timing
(ADR-0005) · **protocol replay** — Probe as SCU against a configured target · fidelity
gate: refuse modes the capture cannot support and say what is missing · replay
provenance: fresh `correlation_id` linked to the original, `replay_id` and
`replay_of_event_id` on events · **guardrails**: dry-run default, target explicitly
configured never inherited from the capture, allowlist required for C-STORE, every run
audit-logged (`12` §10) · exclusivity — one protocol replay at a time, refused not
queued (ADR-0023) · cooperative cancellation reporting how many instances were sent and
confirmed · job records in `app.db`, never auto-resumed (ADR-0023) · golden `.lpcap`
regression harness (ADR-0022 §2).

**Exit.**
- A capture at `fidelity: events` **refuses** protocol replay and names the missing
  stream. Silent degradation here would let someone conclude "it worked on replay" from
  a replay that never sent anything.
- Replay into a non-allowlisted target is refused.
- Restart with a `running` replay transitions it to `Interrupted`; nothing auto-resumes.
- Golden fixture replay yields a byte-comparable event stream and finding set.
- Cancellation reports the confirmed-send count.

**Discharges.** ADR-0005 (replay side), ADR-0023 (jobs), ADR-0022 §2.

## Phase 13 — Viewer

**Objective.** Pixels on screen, with decode timing as evidence rather than a property of
the user's laptop.

**Entry.** Phase 11 exit. (Independent of Phase 12.)

**Work.** Server-side decode via pylibjpeg with optional GDCM, to normalized 16-bit
grayscale plus a JSON sidecar (ADR-0015) · per-instance-per-frame endpoints so multi-frame
and cine stream · server-side LRU frame cache; ±2 prefetch as policy not a hard cap ·
decode in an executor, never on the loop (ADR-0002) · Cornerstone3D as **renderer only**
through a custom image loader · client-side window/level, zoom, pan, invert, cine — the
deliberate minimal-JS exception (ADR-0019) · Study Browser over projections with
**per-instance provenance**, `partial` marking, "present in N captures" (ADR-0013) ·
retention state shown for ring-buffer-backed instances, with inline promotion · duplicate
SOP Instance UID with differing digests surfaced as a finding · offline folder import as a
synthetic capture at `fidelity: objects` · `ImageDisplayed` posted back and quarantined
(ADR-0016) · Metadata Inspector, Transfer Inspector, Event Timeline over existing slices
in `web/` (ADR-0012).

**Exit.**
- Decode duration appears in a capture and a report — it is evidence, reproducible off
  the originating machine.
- A study spanning three captures never renders as whole.
- Ring-buffer-backed instances show retention state and offer promotion.
- Two byte sequences under one SOP Instance UID produce a finding with both digests.
- W/L drag stays within the 100 ms budget with no round trip.
- An undecodable transfer syntax reports *why* — "browser can't show it" and "pixel data
  is broken" must not be indistinguishable.

**Discharges.** ADR-0013, ADR-0015.

## Phase 14 — Analysis

**Objective.** "Explain Everything" (`01` §6) made mechanical, without inference
contaminating evidence.

**Entry.** Phase 12 and Phase 13 exit.

**Work.** **ADR-0028**: Analysis module ownership and the Transfer Analysis / rule engine
boundary (F-03) — first task in the phase, before any rule is written · diagnostic
conditions with stable IDs (`LP-NEG-004`), deterministic, riding the event stream as
`WarningRaised` / `ErrorRaised` (ADR-0018) · **condition ID registry and allocation rule**
(U-04) · findings with rule ID, rule version, confidence, cited sequence numbers,
explanation, next steps — written to `analysis/` in the capture, **never** to
`events.jsonl` · coarse confidence: `certain` / `likely` / `possible`, no invented numeric
precision · analysis as a pure function of (capture, rule-set version); delete and re-run
reproduces · UI links every claim to the events behind it · seed rule set per `01` §3:
rejected associations, no acceptable presentation context, transfer syntax mismatch, slow
C-STORE with per-leg attribution, incomplete studies, missing instances, timeouts and
retries, oversized datasets · C-MOVE out-of-band finding with concrete remediation
(ADR-0024).

**Exit.**
- ADR-0028 accepted before rule work starts.
- Delete `analysis/`, re-run, obtain identical findings.
- Every finding cites sequence numbers that resolve to real events.
- No finding appears in `events.jsonl`.
- Client-asserted events contribute to no finding and no timing (ADR-0016).
- A newer rule set produces better findings against unchanged evidence.

**Discharges.** ADR-0018. **Closes.** F-03, U-04.

## Phase 15 — Reports

**Objective.** A portable artifact, with the safe export as the default.

**Entry.** Phase 14 exit.

**Work.** Report generation via Jinja to HTML and Markdown (`04` §11); **PDF decision**
(U-08) · reports record the rule-set version used (ADR-0018) · tag-level redaction
against a configurable profile with consistent UID remapping, output as a **new** capture
recording source ID and profile (ADR-0026) · terminology discipline: "redact", never
"anonymize" or "de-identified", no PS3.15 claim · explicit warnings for
`BurnedInAnnotation`, Secondary Capture / US / screenshot SOP classes, unrecognized
private tags, free-text fields · **object-dropping as the default handover**: export at
`fidelity: events` with no pixel data · report generation as a background job (ADR-0023).

**Exit.**
- Default export carries no pixel data; pixel-bearing export is a deliberate opt-in.
- Redacted output is a new capture with source provenance; the original is untouched.
- UID remapping is consistent — the Study/Series/Instance hierarchy survives redaction.
- Unverifiable content is flagged, never silently passed.
- No UI string or document claims de-identification.

**Discharges.** ADR-0026. **Closes.** U-08.

## Phase 16 — Plugin SDK

**Objective.** An extension surface proven by using it ourselves.

**Entry.** Phase 14 exit.

**Work.** pluggy hook specifications over `contracts.py` DTOs only, never aggregates
(ADR-0006, ADR-0021) · manifest schema — **disclosure, explicitly not enforcement** ·
plugins ship disabled; enable is restart-scoped because enabling runs code · **no
installation over the API** — filesystem placement plus a CLI command (ADR-0021) ·
exception containment at every hook boundary, `ErrorRaised` with plugin ID, auto-disable
after repeated failure · per-hook time budget reusing ADR-0002's mechanism · SDK
compatibility gate refusing incompatible majors at load · load-time structural validation
· **SDK versioning scheme and deprecation window** (U-09) · **the seed rule set
re-homed as bundled plugins on the public SDK** (ADR-0021, per §3.2 mapping) · plugin
documentation and example plugin.

**Exit.**
- Seed rules run as plugins on the **public** extension points. If they need privileged
  access, the extension points are wrong and this is where we find out.
- A raising plugin never propagates into core; repeated failure disables it.
- A slow plugin produces a warning and is auto-disabled. Documented honestly: we measure
  and disable, we cannot interrupt.
- No API route installs a plugin.
- UI states plainly that an enabled plugin can do anything the process can, and claims no
  capability enforcement.

**Discharges.** ADR-0021. **Closes.** U-09.

## Phase 17 — Observability

**Objective.** One counting path, so metrics cannot disagree with events.

**Entry.** Phase 16 exit.

**Work.** **Metrics derived from the event stream**, not separately instrumented
(ADR-0014) · in-process registry exposed on the API and dashboard · health endpoints per
service, readiness vs liveness (`14` §9, ADR-0007) · per-plugin health, metrics and
version (`14` §15, ADR-0021) · dashboards per `14` §16 · `app.log` as **operational**
logging, not a mirror of domain events (ADR-0014) · correlation IDs shared between logs
and events (`14` §8) · alerting thresholds, configurable (`14` §11) · incident
investigation: timeline reconstruction, evidence preservation (`14` §17) · audit log in
`app.db` covering `12` §10's list.

**Exit.**
- A metric and its underlying event count agree by construction, not by reconciliation.
- "The tool got slow" resolves to a named plugin.
- Health distinguishes readiness from liveness per service.
- `app.log` contains no domain event mirror.
- Prometheus exposition remains absent — deferred to a plugin, no core dependency added.

**Discharges.** ADR-0014 (metrics), ADR-0021 (plugin observability).

## Phase 18 — Production Hardening

**Objective.** Meet the numbers, and make the documentation true.

**Entry.** Phase 17 exit.

**Work.** Performance work against Phase 11's ratified budgets: startup, large-study
handling, event throughput, memory, replay, concurrent clients (`13` §12) · large
Enhanced MR datasets — thousands of instances (`01` §3) · security review: input
validation, path containment, secrets, dependency vulnerability scan (`13` §13) ·
accessibility pass: keyboard-only operation, contrast, scalable typography (`15` §13) ·
**`19-glossary.md` reconciled with the implementation vocabulary** (F-05) · operator
documentation: deployment topologies, reverse-proxy boundary, exposure acknowledgment,
network-filesystem limits, backup targeting `app.db` · troubleshooting guide.

**Exit.**
- Every ratified budget met, or the miss documented and accepted.
- Keyboard-only operation verified for primary workflows; mouse not mandatory (`15` §12).
- Glossary carries ring buffer, promotion, fidelity tier, condition, finding, association
  pair, `.lpcap`, and corrects Study, Replay and Event Store.
- Dependency scan clean or exceptions recorded with rationale.
- Documented HIPAA/GDPR posture states what redaction does and does not claim.

**Closes.** F-05.

## Phase 19 — Packaging

**Objective.** Install paths that work, including the air-gapped one.

**Entry.** Phase 18 exit.

**Work.** Wheel and sdist including committed assets (ADR-0025) · Docker image: exposure
flag set, non-root user, one volume, documented proxy boundary (ADR-0010, ADR-0011) ·
`uv pip install` path requiring **no Node** · vendored asset manifest with versions and
licences (ADR-0025) · data directory version marker and newer-version refusal (ADR-0011)
· upgrade and migration notes — index rebuildable, `app.db` migrated.

**Exit.**
- `uv pip install lumora-probe` then run, on a machine with no Node and no network.
- Docker image runs as non-root with one mounted volume; ownership documented.
- No outbound request on any page load — verified, since `02-alt` §21 promises it and
  ADR-0009 rests on it.
- A data directory from a newer version is refused, not mangled.

**Discharges.** ADR-0025 (distribution).

## Phase 20 — Release

**Objective.** Prove interoperability against implementations we do not control, then
ship.

**Entry.** Phase 19 exit.

**Work.** Interop matrix against DCMTK, dcm4che and Orthanc, run as the **scheduled**
suite (ADR-0022 §4) · multiple modalities and transfer syntaxes, positive and negative
scenarios (`13` §10) · acceptance validation against `02-alt` §26 and `00` §11 · release
notes, versioning, changelog · known-limitations statement: C-MOVE sub-operations, no
authentication, no PS3.15 conformance, plugin trust model.

**Exit.**
- Interop matrix executed and results published, failures triaged.
- Every `02-alt` §26 acceptance item demonstrated.
- `00` §11's Definition of Done satisfied for every shipped feature.
- Limitations documented plainly rather than omitted.

**Discharges.** ADR-0022 §4 (scheduled interop).

---

# 6. Phase-to-ADR coverage

Every ADR is discharged by at least one phase. Foundational records span several.

| ADR | Discharged in |
|-----|---------------|
| 0001 | 01 |
| 0002 | 07 (bus), 10 (ingress), 13 (executor) |
| 0003 | 10 |
| 0004 | 06 |
| 0005 | 11 (capture side), 12 (replay side) |
| 0006 | 05, 07 (registry), 16 (DTOs) |
| 0007 | 04 (lifecycle), 07 (ingress), 11 (recovery), 08 (CLI) |
| 0008 | 11 |
| 0009 | 08 (read-only seam), 10 (DICOM plane), 19 (no telemetry) |
| 0010 | 04 (bind gate), 08 (HTTP), 09 (WS handshake), 19 (Docker) |
| 0011 | 04, 06 (roots), 19 |
| 0012 | 02 |
| 0013 | 06 (projection), 13 (browser) |
| 0014 | 10 (trace), 11 (fidelity), 17 (metrics) |
| 0015 | 13 |
| 0016 | 07 (envelope), 08 (endpoint), 13 (viewer) |
| 0017 | 07 |
| 0018 | 14 |
| 0019 | 09 |
| 0020 | 04 |
| 0021 | 16 |
| 0022 | 03, 05, 12 (golden fixtures), 20 (interop) |
| 0023 | 06 (DB split), 12 (jobs) |
| 0024 | 10 |
| 0025 | 04 (spike), 19 (distribution) |
| 0026 | 15 |

---

# 7. References

`00-architecture-review-findings.md` · `03-dependency-graph.md` ·
`04-milestones.md` · `07-definition-of-done.md` · `08-implementation-order.md` ·
`../adr/` (0001–0026) · `16` §5–§9 · `02-alt` §24.
