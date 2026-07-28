# 03 — Dependency Graph

> **Project:** Lumora Probe
>
> **Document:** Dependency Graph
>
> **Status:** Planning Baseline
>
> **Audience:** Engineering, Architects, Claude Code, Codex

---

# 1. Purpose

This document states what depends on what, where parallelism is genuinely available, and
which dependencies are on the critical path.

It complements `01-work-breakdown-structure.md`, where every task carries an explicit
`Deps` column. Those 310 dependencies were validated mechanically: all resolve to real
task IDs, none references a later phase, and no task ID is duplicated.

---

# 2. Phase dependency graph

```
01 Architecture Review
 └─→ 02 Repository Foundation
      └─→ 03 Development Infrastructure ─────┐
           └─→ 04 Core Infrastructure        │ (threading spike
                └─→ 05 Domain Model          │  feeds Phase 10)
                     └─→ 06 Storage          │
                          └─→ 07 Event System│
                               ├─→ 08 REST API
                               │    └─→ 09 WebSocket
                               │         └─→ 10 DICOM Networking ←┘
                               │              └─→ 11 Capture Engine
                               │                   ├─→ 12 Replay Engine
                               │                   │    └─→ 14 Analysis
                               │                   └─→ 13 Viewer ──┤
                               │                        └──────────┤
                               │                                   └─→ 15 Reports
                               │                                        └─→ 16 Plugin SDK
                               │                                             └─→ 17 Observability
                               └────────────────────────────────────────────────┐
                                                                     18 Hardening
                                                                      └─→ 19 Packaging
                                                                           └─→ 20 Release
```

## 2.1 Why 08 and 09 precede 10

The API and WebSocket layers come before DICOM networking, which looks inverted — the
DICOM edge is the more fundamental capability.

The reason is observability of the thing being built. Once Phase 10 starts relaying real
traffic, the fastest way to see whether relay, negotiation and per-leg timing are correct
is the live event stream and the API. Building the DICOM edge first means debugging it
through logs and unit tests, then rebuilding confidence when the UI arrives.

Phase 08 and 09 depend only on the bus, which Phase 07 delivers. Nothing in them needs
DICOM.

## 2.2 The one genuine circularity, and how it is broken

Three constraints appear to form a cycle:

- Phase 11 (Capture) needs the DICOM edge from Phase 10.
- Phase 10 needs a capture writer to demonstrate anything end to end.
- ADR-0002 defers the pynetdicom threading spike to Phase 11, while ADR-0007's ingress
  design — Phase 07 — depends on the answer.

**Broken by scheduling the spike in Phase 03** (T-03-03-01). The question it answers is
empirical: which thread runs `EVT_C_STORE`, and what blocks. Answering it needs
pynetdicom and a synthetic dataset, not a capture engine. Its output constrains
T-07-02-03's ingress contract and de-risks Phase 10 before either is designed.

The residual Phase 10 ↔ 11 tension is resolved by ordering, not by a cycle: Phase 10
proves itself through the event stream and `pdus.jsonl` writer (T-10-04-01), both of which
depend on Phase 06's storage primitives rather than on Phase 11's ring buffer.

## 2.3 Where 13 diverges from 12

Phase 13 (Viewer) depends on Phase 11, **not** on Phase 12. Replay and the viewer are
independent consumers of a capture. Once Phase 11 exits, both can proceed concurrently —
the single largest parallelism opportunity in the plan, worth roughly 51 tasks of
concurrent work.

Phase 14 (Analysis) is where they rejoin: it needs replay for golden-fixture regression
and the viewer for evidence linking (T-14-03-07).

---

# 3. Critical path

The longest dependency chain, phase-level:

```
01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12 → 14 → 15 → 16 → 17 → 18 → 19 → 20
```

Nineteen of twenty phases. Only Phase 13 sits off it.

That is expected for a system with one event bus at its centre: `03` §5 calls the bus the
heart of the product, and almost everything downstream consumes it.

## 3.1 Task-level critical path

The governing chain through the heaviest work:

| Step | Task | Why it gates |
|------|------|--------------|
| 1 | T-02-02-01 | import-linter contracts; every later slice is placed against them |
| 2 | T-04-03-01 | Error model; every boundary and event references it |
| 3 | T-05-02-01 | `Clock`; ADR-0017's three time concepts and every deterministic test |
| 4 | T-06-02-02 | `events.jsonl` writer; the durable record everything else derives from |
| 5 | T-07-02-01 | Loop-owned bus |
| 6 | T-07-02-04 | Gap-free sequencer; ordering authority for timeline, replay, drop accounting |
| 7 | T-10-02-01 | Relay core; the largest single unknown |
| 8 | T-11-02-02 | Retroactive promotion; the product's differentiating capability |
| 9 | T-12-01-02 | Protocol replay; highest-risk write path |
| 10 | T-14-03-04 | Rule engine; `01` §6's "Explain Everything" |
| 11 | T-16-03-01 | Seed rules on the public SDK; validates the whole extension surface |

**Shortening the path is mostly not available.** Steps 1–6 are strictly sequential by
construction — each supplies a primitive the next assumes. The realistic levers are
starting T-04-05-01 (Cornerstone spike) and T-03-03-01 (threading spike) as early as
possible, since both are investigations whose findings constrain later design, and both
are already scheduled ahead of the work they inform.

---

# 4. Parallelism map

## 4.1 Concurrent phase windows

| Window | Phases that can run concurrently | Concurrent tasks |
|--------|----------------------------------|------------------|
| After 07 exits | 08 REST API | 21 |
| After 09 exits | 10 DICOM (10 has no dependency on 08's resource routes beyond the app) | 22 |
| **After 11 exits** | **12 Replay ∥ 13 Viewer** | **51** |
| After 14 exits | 15 Reports ∥ (16 prep) | 13 + 16 |
| After 17 exits | 18 Hardening — three WPs internally parallel | 19 |

## 4.2 Within-phase parallelism

The `∥` column in the WBS marks per-task safety. Aggregate:

| Phase | Parallel-safe | Serialised | Note |
|-------|---------------|------------|------|
| 04 | 10 | 16 | Config chain serialises; data-root and asset work run wide |
| 06 | 6 | 12 | Schema → mapping → repository is a hard chain |
| 07 | 2 | 13 | Almost fully serial — the bus is one artifact |
| 08 | 13 | 8 | Resource routes are independent of each other |
| 10 | 8 | 14 | Per-service enrichment parallelises; relay core does not |
| 13 | 12 | 18 | Panels parallelise; the decode pipeline does not |
| 14 | 9 | 11 | Seed rules are eight independent tasks |
| 17 | 6 | 4 | Metrics and health are largely independent |
| 18 | 11 | 8 | Performance, security and docs are independent tracks |

Phase 07 is the bottleneck: 13 of 15 tasks serialise because they all modify one
subsystem whose correctness property is global ordering. Adding agents there does not
help. Phases 12 and 16 are similarly serial (17 of 21, 14 of 16) — replay guardrails and
the plugin loader are each one artifact.

## 4.3 Highest-value parallel tracks

1. **12 ∥ 13** — 51 tasks, no shared modules (`replay/` vs `studies/` + `web/`).
2. **Seed rules (T-14-04-01 … 08)** — eight tasks, one module, independent rules.
3. **Resource routes (T-08-02-01 … 07)** — seven tasks, one per slice.
4. **Per-service enrichment (T-10-03-01 … 04)** — four tasks over a shared relay.
5. **Hardening tracks (WP-18-01 ∥ 18-02 ∥ 18-03)** — performance, security, docs.

---

# 5. Cross-cutting dependencies

Some artifacts are depended on far outside their own phase. These are the ones where a
late change is expensive.

| Artifact | Delivered | Depended on by | Cost of late change |
|----------|-----------|----------------|---------------------|
| Error model + code namespace | T-04-03-01 | Every boundary, every condition ID | High — touches every slice |
| `Clock` / `IdGenerator` | T-05-02-01/02 | Every event, every test | Severe — ADR-0022 exists to prevent retrofitting this |
| Event envelope | T-07-01-01 | Every slice, every plugin, the capture format | Severe — it is a wire contract |
| Sequencer | T-07-02-04 | Timeline, replay, drop accounting, integrity checks | Severe |
| `contracts.py` per slice | T-02-01-02, refined per phase | Cross-slice calls, plugin SDK | Moderate — but a leak becomes an ecosystem break |
| Capture manifest | T-06-02-01 | Fidelity gating, promotion, redaction, handover | High |
| Coalescing governor | T-09-02-01 | Both stream endpoints, job progress | Moderate |

**Practical consequence:** the four Severe rows all land in Phases 05–07. That is the
argument for not compressing those phases even though they produce no user-visible
capability.

---

# 6. External dependencies

Points where the plan depends on something outside our control.

| Dependency | First needed | Risk | Mitigation in plan |
|------------|--------------|------|--------------------|
| pynetdicom threading behaviour | T-03-03-01 | High — ADR-0002's design rests on it | Spike scheduled in Phase 03, four phases before the design it constrains |
| pynetdicom relay viability | T-10-02-01 | High — no library-supported proxy mode | Largest single XL task; service-agnostic passthrough limits blast radius |
| Cornerstone3D bundling | T-04-05-01 | Medium — npm ESM graph, not a drop-in | Spike in Phase 04; ADR-0015 shrinks the surface to the render path |
| pylibjpeg codec coverage | T-13-01-01 | Medium — exotic syntaxes are the point | Optional GDCM; T-13-01-06 makes failures explain themselves |
| Tailwind 4 compile step | T-04-05-02 | Low | Committed artifacts + CI staleness check |
| SQLite concurrency behaviour | T-06-01-05 | Low–Medium | Spike; WAL + single writer + network-FS refusal |
| DCMTK / dcm4che / Orthanc | T-20-01-01 | Low | Scheduled suite, deliberately outside the default gate |

---

# 7. Risk-ordered dependency concerns

| # | Concern | Phase | Why it matters | Response |
|---|---------|-------|----------------|----------|
| 1 | Relay proves impractical on pynetdicom as designed | 10 | ADR-0003's inline proxy is the observation model | Threading spike first; permissive standalone mode is a partial fallback that still delivers observation |
| 2 | Ingress contract wrong for real thread behaviour | 07 | Ordering guarantees depend on one boundary | Spike output is an input to T-07-02-03, not a discovery during it |
| 3 | Promotion semantics harder than modelled | 11 | Retroactive promotion is the differentiator | Digest-copy design (ADR-0004) keeps it a copy-and-seal, not a re-scan |
| 4 | Coalescing cannot hold 100 ms under burst | 09 | The only hard number in the PRD | T-09-02-05 tests it in-phase, not at hardening |
| 5 | Cornerstone bundle unusable without its parser | 04 | Would reopen ADR-0015 | Spike in Phase 04; decision documented either way |
| 6 | Index rebuild proves lossy | 06 | Rebuildability underpins ADR-0004, 0011, 0013, 0020, 0023 | T-06-03-03 byte-compares; ADR-0020 and 0023 already carve out the two non-derivable stores |
| 7 | Seed rules need privileged access | 16 | Would mean the SDK is wrong | T-16-03-02 records gaps and fixes the SDK rather than granting privilege |

---

# 8. Scheduling guidance for agents

For an agent picking up work:

1. **Respect the `Deps` column literally.** It was validated; a task whose deps are met
   has everything it needs.
2. **Prefer lowest task ID among available work.** Earlier tasks establish context later
   ones assume.
3. **Never parallelise a task marked `∥ = N` with its siblings.** Those touch one artifact
   whose correctness is global.
4. **P0 before P1 before P2 within a work package.** P0 blocks the work package; P2 can
   slip within the phase.
5. **A phase is not complete until its exit criteria in `02-phase-plan.md` hold** — not
   when its tasks are individually done.

---

# 9. References

`01-work-breakdown-structure.md` · `02-phase-plan.md` · `05-risk-register.md` ·
`08-implementation-order.md` · ADR-0002 · ADR-0003 · ADR-0007 · ADR-0015 · ADR-0022 ·
`03` §5 · `01` §6.
