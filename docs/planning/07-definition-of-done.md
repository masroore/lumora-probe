# 07 — Definition of Done

> **Project:** Lumora Probe
>
> **Document:** Definition of Done
>
> **Status:** Planning Baseline
>
> **Audience:** Engineering, QA, Claude Code, Codex

---

# 1. Purpose

Done at three levels: task, work package, phase. Each level's criteria are checkable by
someone who did not do the work.

`00` §11 requires a Definition of Done per feature. This document supplies it, and `20`
Appendix B's audit at Phase 20 is against these criteria.

---

# 2. Task-level Definition of Done

A task is done when **all** of the following hold. No item is waivable by the implementer.

## 2.1 Implementation

1. The acceptance criteria in the task's `Acceptance` column are met — literally, not
   approximately.
2. Code lives in the module named in the `Module` column. A task that needed to touch a
   different slice is a sign the task was mis-scoped: stop and re-scope rather than
   spreading.
3. No new dependency beyond `04` §13's approved list without an ADR (`04` §15).
4. Public surfaces carry docstrings.
5. Comment density, naming and idiom match the surrounding code.

## 2.2 Boundaries

6. `import-linter` passes. A task that requires relaxing a contract requires an ADR first.
7. No cross-slice import except through `contracts.py`.
8. `domain.py` imports no framework.
9. No `time.` or `uuid.` import outside `core/`.

## 2.3 Tests

10. Tests exist at the layer `01-work-breakdown-structure.md` §2.4 prescribes for what the
    task touched.
11. Tests use the injected `Clock` and `IdGenerator` doubles, never real time or real
    UUIDs.
12. Any concurrency, ordering, drop or crash behaviour the task introduces has an explicit
    adversarial test. These are unverifiable promises otherwise, which is the failure mode
    ADR-0022 §5 exists to prevent.
13. Tests pass. Not "pass locally with one skip" — pass.

## 2.4 Evidence integrity

Four checks specific to this product. A violation here is more serious than a functional
bug, because it corrupts the artifact the product exists to produce.

14. Every event published carries `origin`.
15. Nothing inferred is written to `events.jsonl`.
16. No client-asserted event contributes to analysis, timing, or replay fidelity.
17. Nothing claims anonymization, de-identification, or PS3.15 conformance.

## 2.5 Honesty

18. A failure the task can detect is reported with cause and remediation — never swallowed,
    never silently defaulted (`03` §12).
19. A capability the task cannot deliver for the input given is **refused with an
    explanation**, not silently degraded. Degrading silently is how a user concludes "it
    worked" from a run that did nothing.
20. Any deviation from the baseline is recorded in an ADR before merge (ADR-0001).

## 2.6 Documentation

21. A contract change updates the generated artifact (OpenAPI, event catalog, stream
    contract).
22. A new term is added to the glossary.
23. Temporary files created during verification are removed.

---

# 3. Work-package-level Definition of Done

A work package is done when:

1. Every P0 task in it is done.
2. Every P1 task is done, or explicitly deferred within the phase with a recorded reason.
3. P2 tasks are done or carried, visibly.
4. The work package's tasks integrate — passing individually is not sufficient; the
   subsystem they form works.
5. CI is green on the full suite, not only on the affected tests.
6. Any ADR the work package's preamble names is accepted, not drafted.

---

# 4. Phase-level Definition of Done

A phase is done when:

1. Every work package in it is done.
2. Every exit criterion in `02-phase-plan.md` for that phase is demonstrably met.
3. The phase's milestone criteria in `04-milestones.md` are met, where a milestone attaches.
4. Every deliverable in `06-deliverables.md` for that phase exists and is inspectable.
5. Standing artifacts are regenerated and their drift checks pass.
6. Risks the register assigns to the phase are either mitigated as planned or re-rated with
   a reason.
7. No finding, undefined-behaviour item, or ADR the phase owns remains open.

**A phase is not done because its tasks are individually done.** Exit criteria are separate
on purpose: they test the phase's claim about the system, which no single task establishes.

---

# 5. Quality gates

Mechanical checks. Every one gates; none is advisory.

| Gate | Level | What it checks |
|------|-------|----------------|
| Format | Task | ruff format |
| Lint | Task | ruff check, `18` §5 conventions |
| Static analysis | Task | Type checking; `core`/`shared` at minimum |
| Boundaries | Task | All six import-linter contracts |
| Clock/ID isolation | Task | No `time.` / `uuid.` outside `core/` |
| Unit + component | Task | The layer §2.4 prescribes |
| Adversarial | Task | Concurrency, ordering, drop, crash — where applicable |
| Coverage | Work package | Reported per slice; reviewed, not threshold-gamed |
| Integration | Work package | Full suite green |
| Contract drift | Work package | Event catalog, OpenAPI, assets regenerate identically |
| DICOM component | Phase | Real pynetdicom loopback (Phases 10+) |
| Golden fixture | Phase | Byte-comparable replay (Phases 12+) |
| Performance | Phase | Against ratified budgets (Phases 11, 18) |
| Security | Phase | Input validation, path containment, dependency scan (Phases 04, 08, 18) |
| Interop | Release | Scheduled suite against DCMTK, dcm4che, Orthanc (Phase 20) |

## 5.1 On coverage

Coverage is reported per slice and reviewed, with no global threshold. A threshold rewards
testing hand-written mappers and value objects — exactly the code ADR-0022 says our bugs
are *not* in — while leaving the thread boundary, the JSONL recovery path and the SQLite
concurrency behaviour untested. Review the shape, not the number.

---

# 6. What "verified" means

Three distinctions worth stating, because each is a common way a claim of done turns out
to be false.

**Verified means executed.** A test that was written but not run is not verification. A
build that was not run after an edit is not verification.

**Verified means observed, not inferred.** "The drop counter should match the sequence gap"
is a design intent. "The drop counter matched the sequence gap in this test run" is
verification.

**Unverified is stated, not implied.** If a phase could not run its performance suite
because the environment lacks the traffic generator, that is reported as unverified. A
silent gap in verification is the same class of failure as a silent gap in an event stream —
and this product exists because those are expensive.

For safety-relevant work — anything touching path containment, network exposure, replay
targets, or redaction — state explicitly what was verified and what was not.

---

# 7. Feature-level Definition of Done

For `00` §11's per-feature requirement and Phase 20's audit, a shipped feature is done
when:

1. It works for the inputs it claims to support.
2. It refuses, with an explanation, the inputs it does not support.
3. Its failures name a cause and a next step.
4. It has component-level tests using injected clock and IDs.
5. Its events are in the catalog, with `origin` set.
6. Its errors use the code namespace.
7. It appears in user or operator documentation.
8. Its limitations are documented where a user will encounter them, not only in an ADR.
9. It is reachable from the API, and headless-usable, per `03` §7.
10. It is accessible by keyboard where it has a UI.

---

# 8. References

`01-work-breakdown-structure.md` §2.4 · `02-phase-plan.md` · `04-milestones.md` ·
`06-deliverables.md` · `05-risk-register.md` · `00` §11 · `03` §7, §12 · `04` §13, §15 ·
`13` §15 · `18` §5 · `20` Appendix B · ADR-0001 · ADR-0016 · ADR-0018 · ADR-0022 ·
ADR-0026.
