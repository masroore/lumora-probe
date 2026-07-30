# Phase 14 Completion Report — Analysis

**Review date:** 2026-07-30
**Status:** Complete
**Phase:** 14 — Analysis

## Completed work

Phase 14 makes the Explain Everything contract mechanical while preserving the evidence boundary.
Observed conditions remain deterministic facts; inferred findings are versioned, confidence-labeled,
evidence-linked analysis output stored outside `events.jsonl`.

- Recorded the analysis ownership boundary in ADR-0033: transfer/networking slices own mechanical
  measurements; `analysis/` owns conditions, rules, findings, explanations, confidence, and
  regenerable persistence.
- Added stable `LP-XXX-NNN` condition IDs, duplicate-rejecting allocation registry, deterministic
  observed-condition detection, and the generated condition catalogue.
- Added immutable findings with stable rule identity, rule version, rule-set version, coarse
  `certain`/`likely`/`possible` confidence, sorted unique sequence citations, explanations, and
  concrete next steps.
- Added atomic `analysis/findings.json` persistence. Analysis output never appends to
  `events.jsonl`; delete-and-rerun purity is covered by byte-identical tests.
- Added the evidence-linking workspace inspector. Resolved finding citations link to sequence
  anchors in the captured event timeline; missing UI evidence is shown as unavailable rather than
  rendered as a broken link.
- Centralized observed-event admission so client-asserted events contribute neither conditions,
  inference inputs, nor timing-like monotonic gaps.
- Added the eight bundled seed rule families:
  - rejected association result/source/reason triplets;
  - no acceptable presentation context;
  - transfer syntax mismatch;
  - slow C-STORE with explicit per-leg attribution;
  - incomplete studies and missing instances;
  - timeout/retry patterns within an association pair;
  - oversized datasets with configurable threshold;
  - C-MOVE out-of-band sub-operation flow with ADR-0024 remediation.
- Added `bundled_rules()` with configurable slow-transfer and dataset-size thresholds.

## Design decisions

- `sequence` is the only UI evidence-link target because ADR-0017 makes it the capture's ordering
  authority. Wall-clock timestamps and event IDs are not used as causal anchors.
- The web adapter consumes the public `as_dict()` shape without importing `analysis.domain` or
  `analysis.repository`, preserving import-linter boundaries.
- Rules fail closed when required observed payload fields are absent; missing fields do not become
  invented causal claims.
- Slow-transfer findings identify the affected leg and explicitly avoid end-to-end
  modality-to-PACS assertions required to remain false under ADR-0003.
- C-MOVE findings describe the protocol's out-of-band behavior and recommend either destination-AE
  interception through Probe or C-GET; no hidden relay behavior was introduced.

## Files added or materially modified

- `src/lumora_probe/analysis/rules.py`
- `src/lumora_probe/analysis/service.py`
- `src/lumora_probe/web/workspace_routes.py`
- `src/lumora_probe/web/templates/workspace.html`
- `src/lumora_probe/web/templates/partials/timeline.html`
- `tests/test_phase14_analysis.py`
- `tests/test_phase14_seed_rules.py`
- `docs/planning/phase-14-task-t-14-01-01-report.md`
- `docs/planning/phase-14-task-t-14-02-01-report.md`
- `docs/planning/phase-14-task-t-14-02-02-report.md`
- `docs/planning/phase-14-task-t-14-02-03-report.md`
- `docs/planning/phase-14-task-t-14-03-01-report.md`
- `docs/planning/phase-14-task-t-14-03-02-report.md`
- `docs/planning/phase-14-task-t-14-03-03-report.md`
- `docs/planning/phase-14-task-t-14-03-04-report.md`
- `docs/planning/phase-14-task-t-14-03-05-report.md`
- `docs/planning/phase-14-task-t-14-03-06-report.md`
- `docs/planning/phase-14-task-t-14-03-07-report.md`
- `docs/planning/phase-14-task-t-14-03-08-report.md`
- `docs/planning/phase-14-task-t-14-04-01-report.md` through
  `docs/planning/phase-14-task-t-14-04-08-report.md`
- `docs/generated/condition-catalog-v1.json`
- `docs/condition-catalogue-v1.md`
- `scripts/generate_condition_catalog.py`
- `docs/adr/ADR-0033-analysis-ownership-and-transfer-boundary.md`

## Tests and quality gates

- Full default suite: **437 passed, 2 skipped**.
  - Skips are the expected opt-in interop and browser E2E gates.
- Phase 14 analysis and seed-rule suites: **40 passed** in the final task gate.
- Ruff lint: passed.
- Ruff format check: passed.
- Import-linter: **7 kept, 0 broken**.
- BasedPyright for `core`, `shared`, and `analysis`: **0 errors, 0 warnings, 0 notes**.

## Exit-criterion evidence

| Exit criterion | Evidence |
|---|---|
| ADR-0033 ownership boundary accepted before rule work | ADR-0033 and T-14-01-01 report |
| Delete `analysis/`, rerun, obtain identical findings | `test_analysis_purity_delete_rerun_is_byte_identical_and_newer_rules_add_findings` |
| Every finding citation resolves to a real event | RuleEngine citation validation; UI evidence-link and timeline-anchor tests |
| No finding appears in `events.jsonl` | Analysis repository and purity test preserve source event bytes |
| Client-asserted events contribute no finding or timing | Condition detector, RuleEngine, report, and adversarial exclusion tests |
| Newer rule set improves unchanged evidence | Purity test evaluates a second rule set against unchanged events |
| Seed rule set covers Phase 14 specification | `bundled_rules()` and `tests/test_phase14_seed_rules.py` cover all eight families |

## Known limitations and follow-up

- Event payloads remain intentionally open per the event catalog. Rules accept documented aliases
  for payload fields and fail closed when required evidence is unavailable; future narrow payload
  schemas may reduce alias handling.
- Threshold configuration is available through `bundled_rules()`; application settings wiring and
  report presentation remain owned by later composition/report work.
- Rule execution is deterministic and reusable but does not add a new background orchestration
  path; callers compose `RuleEngine(bundled_rules(...))` with the existing capture and analysis
  repositories.
- Interop and browser gates remain opt-in under the repository testing policy.

## Task commits

- `3e29352` — purity verification
- `370720b` — evidence-linked findings in UI
- `320f699` — client-asserted evidence quarantine
- `8d32b21` — rejected association rule
- `b23d4d1` — missing presentation context rule
- `f738570` — transfer syntax mismatch rule
- `db87741` — slow C-STORE per-leg attribution
- `68a3beb` — incomplete studies rule
- `912b584` — timeout/retry rule
- `47d76c1` — oversized dataset rule
- `b8a5f0c` — C-MOVE out-of-band rule and bundled rule set

The working tree is clean except for the pre-existing untracked local `node_modules/` directory.
