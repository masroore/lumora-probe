# 08 — Implementation Order

> **Project:** Lumora Probe
>
> **Document:** Implementation Order
>
> **Status:** Planning Baseline
>
> **Audience:** Engineering, Claude Code, Codex

---

# 1. Purpose

The execution sequence. This is the document an implementing agent works from: what to
build next, in what order, and what to check before claiming it is done.

The other planning documents answer *why* the order is what it is. This one answers *what
now*.

---

# 2. How to use this document

1. Find the first stage below whose predecessors are complete.
2. Read that stage's rationale — it states what the stage establishes and what breaks if it
   is skipped.
3. Work its tasks from `01-work-breakdown-structure.md` in ID order, respecting the `Deps`
   and `∥` columns.
4. Check the stage's gate before moving on.
5. At a phase boundary, check `02-phase-plan.md` exit criteria and `04-milestones.md`.

Task-level detail is not repeated here. The WBS is authoritative for dependencies,
complexity, priority, module and acceptance.

---

# 3. Execution stages

Twelve stages across twenty phases. A stage is a unit of "you can stop here and the system
is in a coherent state".

## Stage 1 — Decide (Phase 01)

**Tasks** T-01-01-01 … 05

Two decisions gate everything: which file is the PRD (it sits above the ADR layer in
Charter §12, so requirement tracing is meaningless until it is settled), and what the phase
numbers in seven ADRs refer to.

**Gate** M1. ADR-0027 accepted.

## Stage 2 — Enforce (Phases 02–03)

**Tasks** T-02-01-01 … T-03-03-02

Build the skeleton and the machinery that keeps it correct. The order inside is deliberate:
contracts before code, and **proof that each contract fails** before trusting any of them.

Two things here look premature and are not. The synthetic fixture generator comes before
any DICOM work because every later test needs it and because the alternative — real patient
data — must never enter the repository. The pynetdicom threading spike comes seven phases
before relay because its answer constrains the Phase 07 ingress contract; discovering it in
Phase 10 means redesigning the bus.

**Gate** M2, M3. A deliberate boundary violation fails CI. Spike written up.

## Stage 3 — Ground (Phase 04)

**Tasks** T-04-01-01 … T-04-05-06

Config, paths, errors, logging, lifecycle, assets. Nothing user-visible; everything
downstream depends on it.

Order within: config → data root → errors → logging → lifecycle. The exposure gate
(T-04-04-01/02) and path containment (T-04-02-04) belong here rather than in a later
security phase, because in a v1 with no authentication they *are* the security model, and
retrofitting a containment check across every path-accepting route is how one gets missed.

The asset spike (T-04-05-01) runs in parallel with all of it — it is an investigation, and
its answer affects Phase 13.

**Gate** Startup refuses non-loopback bind with an explanation. Traversal test passes.
Network-FS refused. CI fails on stale assets.

## Stage 4 — Model (Phase 05)

**Tasks** T-05-01-01 … T-05-02-04

Value objects, aggregates, and the two injected primitives.

If one stage must be done properly, it is T-05-02-01 through 04. Injected `Clock` and
`IdGenerator` plus the import-linter ban is perhaps two days of work now and a
whole-codebase sweep later. ADR-0022 §1 exists because of exactly this.

**Gate** M4. `time.`/`uuid.` banned outside `core/` and enforced. Both clock halves
independently freezable.

## Stage 5 — Persist (Phase 06)

**Tasks** T-06-01-01 … T-06-03-06

Schemas, capture format, repositories, rebuild.

Order: schemas → connection policy → mapping → repositories → capture writers → rebuild.
The rebuild byte-comparison (T-06-03-03) is the load-bearing test — five ADRs assume
`index.db` is disposable, and this is the only thing that proves it.

**Gate** M5. Delete `index.db`, rebuild, byte-identical projection. Tamper detected.
ADR-0029 accepted.

## Stage 6 — Publish (Phase 07)

**Tasks** T-07-01-01 … T-07-02-08

The bus. Twelve of fifteen tasks serialise, because they all modify one artifact whose
correctness property is global ordering. Adding parallel effort here does not help.

Build the envelope first (T-07-01-01) — it is five ADRs ahead of `06` §6, and every slice
and plugin depends on it. Generate the catalog (T-07-01-05) before anything consumes
events, so eight slices do not each infer the shape.

T-07-02-08 is not optional polish. Split backpressure and gap-free sequencing are promises
about data loss; without the adversarial test they are assertions.

**Gate** M6. Sequence gap matches `EventsDropped` exactly. Capture path never drops.
Catalog published.

## Stage 7 — Expose (Phases 08–09)

**Tasks** T-08-01-01 … T-09-02-05

API then WebSocket. This precedes DICOM deliberately: once Phase 10 relays real traffic,
the fastest way to see whether negotiation and per-leg timing are right is the live stream
and the API. Building the DICOM edge first means debugging it blind.

The access-control seams (WP-08-03) are the entire perimeter in a v1 with no auth. Build
read-only mode as **one** seam so a future auth ADR does not have to move it.

The coalescing governor (WP-09-02) is required, not an optimisation, and its burst test
runs here rather than at hardening — the 100 ms budget is the only hard number in the PRD,
and finding it unachievable in Phase 18 would reopen ADR-0019 far too late.

**Gate** M7. 5,000-event burst within budget. Foreign Host and cross-origin rejected. One
set of partials serving both paths.

## Stage 8 — Observe (Phase 10)

**Tasks** T-10-01-01 … T-10-04-03

The DICOM edge. Highest technical risk in the plan (R-01), de-risked by the Stage 2 spike.

Order: SCP/SCU → relay core → pass-through negotiation → service-agnostic passthrough →
per-service enrichment → PDU trace.

T-10-02-05 deserves attention while writing the relay: a parse-and-re-encode is the natural
implementation and it is wrong. It normalises non-conformant data and destroys the evidence
the user came for. The test asserts bytes are unchanged.

**Gate** M8. C-STORE observed against real pynetdicom. Malformed traffic relayed
unmodified. Unrecognized DIMSE recorded, never aborted. PDU records never on the bus.

## Stage 9 — Preserve (Phase 11)

**Tasks** T-11-01-01 … T-11-04-02

Ring buffer, sessions, promotion, crash recovery, budget ratification.

Retroactive promotion (T-11-02-02) is the product's differentiating capability — the answer
to "the problem happened twenty minutes ago and nobody was recording". Partial marking
(T-11-02-03) is what keeps it honest.

The two recovery tests (T-11-03-03/04) are P0 because durability claims are worth nothing
unverified, and the cost of finding out later is a user's lost capture.

**Gate** M9. Kill-mid-capture recovers and marks `Interrupted`. SIGTERM drains. Budgets
ratified.

## Stage 10 — Investigate (Phases 12–13, parallel)

**Tasks** T-12-01-01 … T-12-05-02 ∥ T-13-01-01 … T-13-04-12

The plan's main parallelism: 51 tasks, no shared modules. Replay touches `replay/` and
`core/jobs.py`; the viewer touches `studies/` and `web/`.

In Phase 12, build the fidelity gate (T-12-01-03) alongside protocol replay, not after. A
replay that silently does nothing lets someone conclude "it worked on replay" — worse than
an error.

In Phase 13, the decode pipeline is serial and the panels are not; the panels are where
parallel effort pays.

**Gate** M10, M11. Golden fixture byte-comparable. `fidelity: events` refuses protocol
replay. Decode duration in an exported report. Partial study never renders whole.

## Stage 11 — Explain (Phases 14–15)

**Tasks** T-14-01-01 … T-15-03-03

Analysis then reports.

ADR-0028 (T-14-01-01) is first, before any rule is written. Without the Transfer Analysis /
rule engine boundary fixed, timing code grows rules inside it and ADR-0018's separation is
lost in practice rather than in principle.

The eight seed rule families parallelise cleanly. `01` §3 is effectively their
specification.

In Phase 15, the terminology audit (T-15-02-05) is P0. The code cannot verify burned-in
annotation, so no string may claim it did.

**Gate** M12. Delete `analysis/`, re-run, identical findings. No finding in
`events.jsonl`. Default export carries no pixels.

## Stage 12 — Harden and ship (Phases 16–20)

**Tasks** T-16-01-01 … T-20-02-05

Plugin SDK, observability, hardening, packaging, release.

T-16-03-01 — porting the seed rules onto the public SDK — is the cheapest way to find out
whether the extension points are wrong. If a first-party analyzer needs privileged access,
the SDK is wrong, and T-16-03-02 records that rather than granting the privilege.

Phase 18's three work packages are independent tracks. Phase 20's interop suite is the
first contact with implementations we do not control; failures get triaged, not omitted.

**Gate** M13, M14. Seed rules on the public SDK. Metric and event counts agree. Clean-machine
no-Node install. Interop published.

---

# 4. Order-critical decisions

Five places where the order matters more than it appears, collected because each is easy to
undo by accident.

| # | Decision | Undone by | Consequence |
|---|----------|-----------|-------------|
| 1 | Threading spike in Phase 03 | Deferring it to Phase 11 per ADR-0002 | Phase 07's ingress contract designed on an assumption; bus redesign |
| 2 | Injected clock/ID in Phase 05 | "We'll add it when we need determinism" | Whole-codebase sweep; ADR-0022 §1 exists for this |
| 3 | Envelope + catalog before consumers | Letting slices infer the shape | Eight divergent interpretations of a wire contract |
| 4 | API/WS before DICOM | Building the edge first because it seems fundamental | Debugging relay blind, then re-establishing confidence |
| 5 | Read-only mode as one seam | Per-route checks | A future auth ADR must move every check; one gets missed |

---

# 5. Standing rules during implementation

1. **Refuse, don't degrade.** Any capability that cannot be delivered for the given input is
   refused with an explanation. This is the single most repeated requirement across the
   ADRs, and the most common way this class of tool becomes untrustworthy.
2. **`origin` on every event.** No exceptions; absence is a validation error.
3. **Nothing inferred in `events.jsonl`.** Findings live in `analysis/`.
4. **Never claim de-identification.** "Redact" only.
5. **No new dependency without an ADR.** `04` §13, §15.
6. **No baseline document edits.** Deviations go in ADRs (ADR-0001, `17` §12).
7. **Adversarial tests for concurrency, ordering, drops and crashes.** Otherwise those
   guarantees are assertions.
8. **Report what was not verified.** A silent gap in verification is the same failure class
   as a silent gap in an event stream.

---

# 6. Entry point

Nothing is built yet. Start at **Stage 1, T-01-01-02** — ADR-0027, the authoritative PRD.
T-01-01-01 (this review) and T-01-01-04 (phase reconciliation) are already delivered.

---

# 7. References

`00-architecture-review-findings.md` · `01-work-breakdown-structure.md` ·
`02-phase-plan.md` · `03-dependency-graph.md` · `04-milestones.md` ·
`05-risk-register.md` · `06-deliverables.md` · `07-definition-of-done.md`.
