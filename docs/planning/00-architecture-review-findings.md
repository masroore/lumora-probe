# 00 — Architecture Review Findings

> **Project:** Lumora Probe
>
> **Document:** Pre-Implementation Architecture Review
>
> **Status:** Planning Baseline
>
> **Audience:** Architects, Engineering, QA, Product, Claude Code, Codex

---

# 1. Purpose

The build brief requires an architecture review **before** the implementation plan, and
requires that inconsistencies be **documented rather than corrected**. This document is
that review.

It covers all 21 documents in `../architecture-baseline/` and the 26 records in
`../adr/`. No baseline document was modified in producing it.

## 1.1 How to read this

Findings are classified:

| Class | Meaning | Action |
|-------|---------|--------|
| **RESOLVED** | A conflict or gap the ADR layer already decides | None; cited for traceability |
| **OPEN** | A genuine gap that no ADR closes; blocks or shapes work | Named owner phase in `02-phase-plan.md` |
| **WATCH** | Not a defect now; will become one under a named future condition | Revisit at the trigger |

Baseline documents are cited by number, matching the ADR convention: `06` §9 =
`06-event-driven-architecture.md` section 9. `00` is the Charter, `01` the Product
Vision, `02` the PRD. `Lumora-Probe-PRD.md` is cited as `02-alt` (see F-01).

---

# 2. Headline assessment

The baseline is unusually clear about **what** the product is and unusually thin about
**how** it works. That asymmetry is itself the most important finding, and ADR-0001
already names it: only `06-event-driven-architecture.md` is normative. The other 20
documents are, in the main, checklists of section headings — `07` §7 lists what each
entity "should define" and then defines no field of any entity; `11` §6 states outright
that "physical schema is intentionally unspecified".

**The ADR layer has done the heavy lifting.** Of the substantive conflicts a reader hits
in the baseline, 26 ADRs resolve the great majority, and they do it with reasoning that
holds up — several correct real errors rather than papering over them (ADR-0014
explicitly retracts a wrong cost claim made in ADR-0005; ADR-0017 shows that `06` §9's
ordering instruction is unsafe as written).

**The planning-layer conclusion: implementation is not blocked.** What remains is a
small number of real gaps, listed in §4, plus one structural gap that this planning set
itself closes (F-02: the phase numbering the ADRs already cite did not exist as a
document).

Consequently `01-work-breakdown-structure.md` proceeds. Per ADR-0001, Phase 01 delivers
this review and a gap register, **not** a stop-the-line report.

---

# 3. Resolved findings — recorded for traceability

These read as contradictions in the baseline. Each is already decided. Implementers
should follow the ADR and not attempt to reconcile the baseline text.

| ID | Baseline tension | Resolution |
|----|------------------|------------|
| R-01 | `03` §4 domain "framework independent" vs `04` §4 Pydantic for "domain validation" | ADR-0006 — plain-Python domain, Pydantic at boundaries |
| R-02 | `03` §4 four layers vs `05` §21/§24 module contracts | ADR-0012 — module-first slices, layers as import-linter rules |
| R-03 | `04` §5 endpoint capabilities vs `02` §2 "think Wireshark" | ADR-0003 — inline proxy on an endpoint foundation |
| R-04 | `05` §7 session captures vs `01` §4 "capture every important event" | ADR-0008 — ring buffer plus promotable sessions |
| R-05 | `07` §4 Study as top-level aggregate vs `00` §6 "not a PACS archive" | ADR-0013 — Study/Series/Instance are projections |
| R-06 | `06` §9 order by `occurred_at` — unsafe; wall clock is not monotonic | ADR-0017 — gap-free `sequence` is the sole ordering authority |
| R-07 | `06` §10 durable persistence vs `09` §12 event dropping | ADR-0002 — split by purpose; capture path never drops |
| R-08 | `09` §8 JSON envelope vs `04` §7 HTMX/minimal-JS | ADR-0019 — two endpoints, one bus source |
| R-09 | `04` §5 server codecs vs `04` §7 Cornerstone3D client codecs | ADR-0015 — server decodes, client renders |
| R-10 | `02` §21 optional auth vs `12` §3/§7 secure-by-default + RBAC | ADR-0009 / ADR-0010 — no auth in v1, loopback + exposure gate |
| R-11 | `10` §13 / `12` §11 enforced plugin capabilities vs `04` §10 in-process pluggy | ADR-0021 — trusted code; manifest is disclosure |
| R-12 | `02` §20 four log sinks vs hot-path cost | ADR-0014 — one durable event record; `app.log` is operational |
| R-13 | `05` §10 Viewer publishes `ImageDisplayed` vs evidence integrity | ADR-0016 — admitted, quarantined by mandatory `origin` |
| R-14 | `13` §4 unit-heavy pyramid vs where this system's bugs live | ADR-0022 — component-weighted |
| R-15 | `08` §3 "HTTPS exclusively" vs local-first usability | ADR-0009 — superseded; TLS at reverse proxy |
| R-16 | `04` §13 no brokers vs `03` §16 distributed collectors | ADR-0007 — one process, transport-abstracted ingress |
| R-17 | `04` §4 env-over-file precedence vs `05` §17 UI-editable settings | ADR-0020 — two tiers, provenance-tagged |
| R-18 | `11` §5 capture repository and event store unrelated | ADR-0004 — capture directory; DB is a rebuildable index |
| R-19 | `06` Appendix A lists `CMoveRequested` as if relayable | ADR-0024 — service-agnostic relay; C-MOVE partially observable |
| R-20 | `07` §21 / `12` §9 require redaction, neither defines it | ADR-0026 — honest partial redaction; object-dropping default |

---

# 4. Open findings

These are not closed by any ADR. Each carries an owning phase.

## F-01 — Two PRDs coexist with no precedence rule · **OPEN** · High

`docs/architecture-baseline/` contains both `02-product-requirements-document.md` and
`Lumora-Probe-PRD.md`. Both call themselves the PRD. Charter §12 ranks "the PRD" second
in the hierarchy, above ADRs — so which file that is, is load-bearing.

They are not duplicates. `Lumora-Probe-PRD.md` is the more specific of the two and is
the **only** source for several constraints the ADRs depend on:

- §22 performance targets (UI < 100 ms, current ±2 images decoded) — cited by ADR-0015
  and ADR-0019
- §20 the four output sinks — the statement ADR-0014 rejects
- §21 "Local-first · No outbound telemetry" — cited by ADR-0009
- §13 Transfer Inspector field list — cited by ADR-0015 and ADR-0017
- §24 an **eight-phase** roadmap
- Appendix repository structure — cited by ADR-0011

`02-product-requirements-document.md` §10 meanwhile describes itself as awaiting 18
further chapters that do not exist, and its §5 lists 13 modules against `05`'s 16.

Practical effect: every ADR citation of the form `02` §NN resolves against
`Lumora-Probe-PRD.md`, not against `02-product-requirements-document.md`. The ADR README
says "`02` the PRD" without disambiguating.

**Recommendation:** treat `Lumora-Probe-PRD.md` as the authoritative PRD (it is the one
the ADRs actually cite and the only one with testable requirements), and reclassify
`02-product-requirements-document.md` as a PRD outline. This needs an ADR because it
touches the Charter §12 hierarchy. Owner: **Phase 01**.

## F-02 — The phase numbering the ADRs cite had no defining document · **OPEN → closed by this planning set** · High

Seven ADRs commit work to numbered phases:

| ADR | Phase cited | Work committed |
|-----|-------------|----------------|
| ADR-0001 | Phase 01 | Compliance review and gap register |
| ADR-0025 | Phase 04 | Cornerstone3D bundling spike |
| ADR-0007 | Phase 05 | (rejected alternative: bespoke broker) |
| ADR-0022 | Phase 05 | `Clock` / `IdGenerator` injection |
| ADR-0007 | Phase 12 | Crash-recovery path built and tested |
| ADR-0002 | Phase 11 | pynetdicom threading spike |
| ADR-0005 | Phase 13 | Event replay and protocol replay |
| ADR-0021 | Phase 17 | Seed rule set as bundled plugins |

No baseline document defines phases by those numbers. `16` §5–§9 gives **five** named
phases; `02-alt` §24 gives **eight**. Neither matches.

The brief's own illustrative 20-phase list does match, on every one of the seven
citations:

- Phase 01 Architecture Review ✓ (ADR-0001)
- Phase 04 Core Infrastructure ✓ (ADR-0025, asset pipeline)
- Phase 05 Domain Model ✓ (ADR-0022, `Clock`/`IdGenerator` as core protocols)
- Phase 11 Capture Engine ✓ (ADR-0002, DICOM edge threading)
- Phase 12 Replay Engine — ADR-0007 places crash recovery here ⚠ (see below)
- Phase 13 Viewer — ADR-0005 places replay here ⚠ (see below)
- Phase 17 Observability — ADR-0021 places the seed rule set here ⚠ (see below)

Five of seven land exactly. Three sit one to four positions off their apparent subject,
which is evidence the ADR authors were writing against a **slightly different** 20-phase
list than the brief's illustration — most likely one where Replay precedes Viewer and
Plugin SDK sits at 17.

`02-phase-plan.md` adopts the brief's 20-phase numbering as canonical and records the
three off-by-N citations as known drift, mapping each to its true phase. No ADR is
rewritten. Owner: **closed by `02-phase-plan.md` §3.2**.

## F-03 — Analysis has no owning module in `05` · **OPEN** · Medium

ADR-0018 is one of the most consequential records — it separates observed conditions
from inferred findings, defines rule IDs, versioning and confidence levels, and makes
analysis a pure function of (capture, rule-set version). ADR-0012 gives it a package
slice (`analysis/`). ADR-0021 makes the seed rule set ship as bundled plugins.

But `05`'s ownership matrix (§22) has no Analysis row, and `05` §12 assigns
recommendation-publishing to **Transfer Analysis**, which is a different and narrower
thing. So the rule engine — a significant subsystem — has an ADR, a package and no
baseline owner.

Consequence for planning: the boundary between "Transfer Analysis computes per-leg
timing" and "the rule engine infers why it was slow" needs stating before either is
built, or the timing code will grow rules inside it. Owner: **Phase 14**, with the
boundary fixed in that phase's entry criteria.

## F-04 — No versioned event catalog artifact exists · **OPEN** · Medium

`06` is normative and names events across ten categories (§5, Appendix A). ADR-0006
requires a payload-model registry keyed by `(event_name, event_version)`. ADR-0014
splits domain events from protocol trace records and adds derived summary fields.
ADR-0016 adds a mandatory `origin` field. ADR-0017 adds `monotonic_ns` and `sequence`.
ADR-0005 adds `replay_id` and `replay_of_event_id`.

So the envelope in `06` §6 is now **five ADRs out of date**, and no single document
states the current one. Every slice publishes events; every plugin consumes them; the
capture format is defined by them.

This is not a conflict — the additive changes are all permitted by `06` §8 — it is a
missing artifact. The catalog needs to exist as generated, versioned output before
Phase 07 ships, or eight slices will each infer the envelope independently. Owner:
**Phase 06** (`shared/` envelope + registry), generated catalog as a deliverable.

## F-05 — `19-glossary.md` predates the ADR vocabulary · **OPEN** · Low

The glossary defines `Study` as "a DICOM Study consisting of one or more Series"
(ADR-0013 made it a projection), `Replay` as "re-execution of captured events"
(ADR-0005 defines three distinct meanings and ships two), and `Event Store` as a
storage term (ADR-0004 replaced it with a capture directory plus rebuildable index). It
has no entry for ring buffer, promotion, fidelity tier, condition, finding, association
pair, or `.lpcap`.

`18` §7 requires names that "clearly express intent" and `19` §1 aims for shared
vocabulary across documentation and code. A glossary that disagrees with the
implementation vocabulary is worse than none, because it will be cited. Owner:
**Phase 18**, as a documentation deliverable rather than a blocker.

## F-06 — Non-functional targets are stated for the UI only · **OPEN** · Medium

`02-alt` §22 gives exactly one hard number: UI responsive < 100 ms. `13` §12 lists what
to assess (startup time, large study handling, event throughput, memory, replay
performance, concurrent clients) without a target for any of them. `14` §12 likewise.

ADR-0014 supplies the only quantified capacity figures anywhere in the corpus — ~5,000
domain events per 500-instance study, ~16,000 PDUs, ring buffer 30 min / 2 GB — but
these are stated as reasoning, not as acceptance thresholds.

Without numbers, `13` §12's performance tests cannot fail, and "the bus stalled" cannot
be the testable regression ADR-0014 claims it becomes. Recommendation: derive
provisional budgets from ADR-0014's figures during Phase 03, ratify them against real
traffic in Phase 11, and treat them as release gates thereafter. Owner: **Phase 03**,
ratified **Phase 11**.

## F-07 — Charter §5 promises a CLI that no baseline document specifies · **OPEN** · Low

`00` §5 lists CLI in product scope and `03` §7 requires all functionality to be
available headless. ADR-0007 settles the CLI's *architecture* (a client over
`/api/v1`, with one-shot embedded execution allowed for offline work) and ADR-0021
makes plugin install CLI-only, which makes the CLI load-bearing for a security
decision.

No document specifies its command surface. `08` and `09` cover REST and WebSocket; no
equivalent exists for the CLI. Recommendation: specify the command surface as a
Phase 08 deliverable derived from the API resource catalog, plus the two ADR-mandated
offline commands. Owner: **Phase 08**.

## F-08 — `Instance` ownership is stated twice, incompatibly · **OPEN** · Low

`07` §11 requires every entity to have exactly one owning aggregate. `07` §10's tree
places `Instance` under `Study → Series`, and `Capture` owns `Events / Logs / Analysis`
with no instances. ADR-0013 resolves the aggregate question (projection) and ADR-0004
resolves the byte question (`objects/` inside a capture, content-addressed).

What is *not* resolved: `07` §10 also says "ownership, lifecycle, and cascade behavior
shall be explicitly defined", and cascade is genuinely undefined for the case ADR-0013
creates — a study spanning three captures where one is deleted. The projection row
disappears, which ADR-0013 states; whether bookmarks referencing it, findings citing
it, and reports embedding it are pruned, orphaned, or annotated is not stated anywhere.
Owner: **Phase 06**, cascade semantics as an explicit design task.

---

# 5. Watch items

Not defects today. Each has a stated trigger.

| ID | Item | Trigger that makes it a defect |
|----|------|-------------------------------|
| W-01 | `06` §9 disclaims global ordering; ADR-0017 scopes `sequence` per capture | Remote collectors (ADR-0007 deferred) — cross-collector ordering claims must stay refused |
| W-02 | ADR-0021 cannot interrupt a looping plugin | First third-party plugin ships; an infinite loop stalls the loop and no in-process fix exists |
| W-03 | `time.monotonic()` excludes suspended time on macOS, not Linux (ADR-0017) | Cross-platform capture comparison; `ClockAnomalyDetected` must be surfaced, not smoothed |
| W-04 | Two stores kept coherent by convention (ADR-0004) — JSONL has no referential integrity | Index rebuild proves lossy for anything not re-derivable; ADR-0020 and ADR-0023 already carve out settings and job history |
| W-05 | Committed build artifacts (ADR-0025) | Any contributor path that edits templates without running the asset build; CI staleness check is the only guard |
| W-06 | `12` §17 names HIPAA/GDPR; ADR-0026 explicitly claims no PS3.15 conformance | A deployment treats "redact" as de-identification; the naming discipline is the only control |
| W-07 | ADR-0003 makes Probe a live-path failure point | First production inline deployment; pass-through fidelity and byte-faithful relay are the mitigations |

---

# 6. Circular dependency check

The brief asks specifically for circular dependencies. Assessed at three levels.

**Module level — none.** ADR-0012's import-linter contracts are acyclic by
construction: `core` imports no slice, `shared` imports only `core`, slices import
`core`/`shared`/other slices' `contracts.py`, `web` imports slices and nothing imports
`web`. The contracts are machine-checked, so this stays true rather than decaying.

**Document level — two cycles, both benign.** `06` ↔ `07` cite each other (events ↔
aggregates), as do `08` ↔ `09`. Both are cross-references between peer specifications,
not dependency inversions.

**Decision level — one resolved cycle worth noting.** ADR-0005 constrained the capture
format retroactively (it required PDU recording, which changed ADR-0004's output), and
ADR-0014 then retracted ADR-0005's cost estimate and moved PDU records off the bus
entirely. The chain 0004 → 0005 → 0014 → 0004 reads circular but is sequential
correction, and the ADRs say so explicitly. No action.

**One near-cycle to hold at planning level:** Phase 11 (Capture) needs the DICOM edge,
Phase 10 (DICOM Networking) needs the capture writer to prove anything end-to-end, and
ADR-0002 defers the pynetdicom threading spike to Phase 11 while ADR-0007 depends on
the answer for its ingress design. `03-dependency-graph.md` breaks this by scheduling
the spike as a Phase 03 investigation with its findings feeding Phase 10 — the spike
answers an empirical question and does not need the capture engine to exist.

---

# 7. Areas requiring new ADRs

Two classes: gaps this review found, and deferrals the ADR layer already declared.

## 7.1 From this review

| Proposed | Subject | Finding | Needed by |
|----------|---------|---------|-----------|
| ADR-0027 | Which file is the authoritative PRD | F-01 | Phase 01 |
| ADR-0028 | Analysis module ownership; Transfer Analysis vs rule engine boundary | F-03 | Phase 14 |
| ADR-0029 | Cascade semantics for cross-capture projections | F-08 | Phase 06 |
| ADR-0030 | Non-functional budgets as release gates | F-06 | Phase 03 |

## 7.2 Already deferred by the ADR layer

Carried forward verbatim from `../adr/README.md`; each needs its own ADR before
implementation. Listed here so the WBS does not silently schedule any of them.

pcap import plugin (0003) · byte-exact / mock-peer replay (0005) · remote collectors
(0007) · multi-user auth and RBAC (0009) · plugin installation over the API (0021) ·
config profiles (0020) · DIMSE-N enrichment (0024) · Prometheus exposition as a plugin
(0014) · PS3.15 de-identification profile as a plugin (0026)

---

# 8. Undefined behaviour inventory

Points where an implementer will otherwise invent semantics. Each is assigned in the
WBS rather than left to discretion.

| # | Undefined | Owner phase |
|---|-----------|-------------|
| U-01 | Physical schema for `index.db` and `app.db` (`11` §6 explicitly declines) | Phase 06 |
| U-02 | Pagination defaults and maximum page size (`08` §10 lists parameters only) | Phase 08 |
| U-03 | Error code namespace and remediation text (`03` §12 requires guidance, no scheme) | Phase 04 |
| U-04 | Diagnostic condition ID registry — ADR-0018 shows `LP-NEG-004`, defines no allocation rule | Phase 14 |
| U-05 | Retention policy semantics beyond the ring buffer (`11` §10 requires configurable) | Phase 06 |
| U-06 | Health check readiness vs liveness split (`14` §9 says "where appropriate") | Phase 04 |
| U-07 | WebSocket heartbeat interval and idle timeout (`09` §10 lists mechanisms only) | Phase 09 |
| U-08 | Report output formats — `04` §11 gives Jinja for HTML/Markdown; PDF unaddressed | Phase 15 |
| U-09 | Plugin SDK versioning scheme and deprecation window (`10` §12 requires policy) | Phase 16 |
| U-10 | `.lpcap` format version and forward-compatibility rule for readers | Phase 11 |

---

# 9. Compliance statement

Per the brief:

- The architecture was analysed before the implementation plan. ✓
- Inconsistencies are documented, not corrected. No baseline file was modified. ✓
- Findings precede the WBS in document order and in `08-implementation-order.md`. ✓
- Gaps requiring ADRs are named with proposed numbers and owning phases. ✓
- Circular dependencies were assessed at module, document and decision level. ✓

**Verdict: proceed to implementation planning.** Eight open findings, four of which
need an ADR, none of which blocks Phase 02. F-02 is closed by `02-phase-plan.md`.

---

# 10. References

All 21 documents in `../architecture-baseline/`, all 26 records in `../adr/`.

Cited most heavily: `00` §5, §6, §12 · `01` §3, §4, §6 · `02-alt` §13, §20, §21, §22,
§24 · `03` §4, §7, §12, §16 · `04` §4, §5, §7, §10, §13 · `05` §7, §12, §21, §22, §24 ·
`06` §3, §6, §8, §9, §10 · `07` §4, §7, §10, §11, §21 · `08` §3, §10, §12 · `09` §8,
§10, §12 · `10` §12, §13 · `11` §5, §6, §10 · `12` §3, §7, §11, §17 · `13` §4, §12,
§14 · `14` §9, §12 · `16` §5–§9 · `19` §3.
