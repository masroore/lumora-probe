# Phase 18 — Production Hardening: Implementation Plan

**Date:** 2026-07-31
**Status:** Draft — awaiting approval (do not implement until ratified)
**Predecessor:** Phase 17 (Observability) — complete
**Milestone:** M13 — Release Candidate (`04-milestones.md`)
**Governing docs:** `02-phase-plan.md` §Phase 18, `01-work-breakdown-structure.md` C-18,
`06-deliverables.md` §Phase 18, `13-testing-strategy.md` §12–13, `15-ui-ux-guidelines.md` §12–13,
`12-security-architecture.md`, ADR-0004, ADR-0005, ADR-0008, ADR-0010, ADR-0011, ADR-0013,
ADR-0022, ADR-0026, ADR-0030, ADR-0031

---

## Corrections applied against planning assumptions

| Planning assumption | Reality (Phase 17 exit) |
|---|---|
| "Performance work against Phase 11's ratified budgets" for startup / large study / throughput / memory / replay / concurrent clients | **ADR-0030 ratifies capture volume + ring retention only.** Those other dimensions remain unratified. Phase 18 exit allows "miss documented and accepted." |
| F-06 closed by T-11-04-02 | **Partially closed.** Capture/retention gates are release commitments; UI <100 ms is still provisional; startup/throughput/memory/replay/clients have no numbers. `00-architecture-review-findings.md` still labels F-06 OPEN (stale label, partial truth). |
| T-18-01-07 Virtualized tables depends on T-13-04-08 (Search panel) | **Search panel was deferred from Phase 13 and never landed in Phase 14.** Tabulator is vendored but unused. No search/table host exists in `src/`. |
| Security / a11y / dependency scan are greenfield | **Foundations exist.** Path containment, `SecurityMiddleware`, logging/settings redaction, ARIA workspace, command palette, `pip-audit --strict` in CI. Phase 18 is primarily measure, verify, document, and close gaps. |
| Operator docs already exist | **Partial.** `docs/guides/vendor-handover.md` and `docs/capture-engine.md` exist. Deployment topology, operator guide, troubleshooting guide, persona user docs, and HIPAA/GDPR posture statement are missing. |

---

## 0. Pre-phase gate: budget posture (must decide before WP-18-01 coding)

Phase 18 cannot "meet the numbers" where no numbers exist. Three options; **recommended: B**.

### Option A — Ratify additional budgets first (new ADR)

Measure under synthetic load, then publish ADR-0032 (or amend ADR-0030) with release gates for:

| Dimension | Candidate gate (to be measured, not assumed) | Basis |
|---|---|---|
| Startup (cold `lumora serve` to `/api/v1/health` ready) | TBD after measurement; candidate ≤3 s on reference laptop | Lite NFR-01 is <1 s for *lite* tools only — do not copy blindly |
| Large study (Enhanced MR scale) | Index/list/browse 2,000+ synthetic instances without OOM; UI remains interactive | `01` §3, PRD §22 |
| Event throughput | Sustained publish of ratified cardinality without bus stall; UI drops accounted via `EventsDropped` | ADR-0002, ADR-0030 |
| Memory | RSS bounded under sustained ring-fill + capture; no unbounded growth after eviction | ADR-0008 |
| Replay | Protocol replay of 500-instance capture completes; timing fidelity assertions from Phase 12 preserved | Phase 12 suite |
| Concurrent clients | Desktop-scale (`15` §15): N WebSocket UI clients without silent failure | ADR-0019 drop-oldest + counter |
| UI interaction | Promote provisional <100 ms coalescing flush (already tested loop-side) or document as non-release | F-06 / provisional budgets |

**Pros:** Honest release gates. **Cons:** Blocks coding until measurement + ADR review.

### Option B — Measure, gate what is ratified, document accepted misses (recommended)

1. Keep ADR-0030 gates as hard CI failures (already covered by `tests/test_phase11_budgets.py`).
2. Add a Phase 18 performance suite that **records** startup / large-study / throughput / memory / replay / concurrent-client measurements against *candidate* thresholds.
3. For each dimension: either (i) promote to a new ADR with evidence, or (ii) record an accepted miss in the Phase 18 completion report + operator guide with workload identity and what was not verified (required by provisional budgets §Guardrail).
4. Do **not** invent hard CI gates for unratified numbers without an ADR.

**Pros:** Matches Phase 18 exit wording; avoids fake precision. **Cons:** Some dimensions may ship as documented limitations rather than gates.

### Option C — Defer all unratified perf work to a later milestone

**Rejected:** Phase 18 exit explicitly requires the assessment; documentation-only without measurement fails `13` §12.

**Gate resolution required before WP-18-01 implementation begins.** Default if approved without comment: **Option B**.

---

## 1. Current state inventory (verified)

| Area | Location | Status |
|---|---|---|
| ADR-0030 budgets | `docs/adr/ADR-0030-*.md`, `tests/test_phase11_budgets.py` | EXISTS — capture/retention only |
| Ring buffer / promotion | `docs/capture-engine.md`, captures slice | EXISTS |
| Production bootstrap | `src/lumora_probe/bootstrap.py`, `lumora serve` | EXISTS (Phase 17) |
| Path containment | `core/paths.py` | EXISTS |
| HTTP security | `web/security.py`, `tests/test_phase08_security.py` | EXISTS |
| Secret redaction | `core/logging.py`, `settings/runtime.py`, `reports/redaction.py` | EXISTS |
| `pip-audit --strict` | `.github/workflows/ci.yml` | EXISTS (Python); npm audit manual only |
| ARIA / command palette | `web/templates/workspace.html`, `assets/source/command-palette.js` | EXISTS |
| High-contrast theme | `assets/source/app.css` | MISSING (light/dark/system only) |
| Keyboard-only e2e gate | Playwright suite | MISSING |
| Tabulator / virtualized tables | `assets/vendor/tabulator.min.js` | Vendored, unused |
| Search panel | — | MISSING (deferred, never shipped) |
| Glossary reconciliation | `19-glossary.md` | PARTIAL — F-05 open |
| Deployment / operator / troubleshooting guides | `docs/guides/` | MISSING (handover + capture-engine only) |
| HIPAA/GDPR posture doc | — | MISSING (ADR-0026 is technical, not operator posture) |

---

## 2. Work package overview

| WP | Name | Tasks | Parallelism | Notes |
|---|---|---|---|---|
| WP-18-01 | Performance | T-18-01-01 … T-18-01-07 | Mixed | Budget posture gate first |
| WP-18-02 | Security and accessibility | T-18-02-01 … T-18-02-07 | Mixed | Mostly verify + close gaps |
| WP-18-03 | Documentation | T-18-03-01 … T-18-03-05 | Docs-heavy | Closes F-05; posture statement |

Recommended commit order: **18-02 security path re-verify (quick wins) ∥ 18-03 glossary** → **18-01 measurements** → **18-02 a11y** → **18-03 operator docs** → completion report.

Independent tracks may fan out after the budget posture decision.

---

## 3. WP-18-01 — Performance

### T-18-01-01 — Startup time

**Work.** Instrument cold start of `build_production_app()` / `lumora serve` to first successful `GET /api/v1/ready` (or `/health` ready). Record wall time under injected clock where possible; wall clock acceptable for this measurement only (not for event ordering).

**Acceptance.** Measurement recorded with machine class and workload identity. Against ratified budget if Option A; else candidate threshold + pass/miss documented (Option B).

**Tests.** `tests/test_phase18_startup.py` (component; mark `slow` if needed).

### T-18-01-02 — Large study handling (P0)

**Work.** Synthetic Enhanced-MR-scale fixture: **≥2,000 instances** via existing fixture generator patterns (UID namespace `1.2.826.0.1.3680043.10.543.*` only). Exercise study browser / index projection / instance listing without loading all pixels. Assert no OOM and bounded response for metadata browse.

**Must not.** Decode all pixels; claim clinical viewer performance; use real patient data.

**Acceptance.** Thousands-of-instances path completes; documented memory/time; failures are explicit.

**Tests.** `tests/test_phase18_large_study.py` (`slow`, synthetic only).

### T-18-01-03 — Event throughput under load (P0)

**Work.** Sustained bus publish at ADR-0030 cardinality scale. Assert capture path does not drop; UI channel drops equal `EventsDropped` and sequence gaps (existing adversarial pattern). Bus must not stall past a documented bound for the test harness.

**Acceptance.** Drops accounted; capture durable path intact; result recorded.

**Tests.** Extend or add `tests/test_phase18_throughput.py` (component + adversarial).

### T-18-01-04 — Memory profile

**Work.** After ring-fill past eviction thresholds, assert RSS / process memory does not grow without bound across N eviction cycles (platform-appropriate measurement; document tool).

**Acceptance.** Bounded under sustained capture; miss documented if measurement noise prevents hard gate.

### T-18-01-05 — Replay performance

**Work.** Time protocol replay of a 500-instance capture. Preserve Phase 12 timing-fidelity assertions. Do not invent new fidelity tiers.

**Acceptance.** Completes within recorded bound; Phase 12 suite still green.

### T-18-01-06 — Concurrent client load

**Work.** N concurrent `/ws/ui` (and optionally `/api/v1/events/stream`) clients at desktop scale. Assert drop accounting and no silent failure.

**Acceptance.** Documented N; counters honest.

### T-18-01-07 — Virtualized tables

**Dependency break.** T-13-04-08 (Search) never shipped. Resolution options:

| Option | Action | Recommendation |
|---|---|---|
| **V1** | Apply Tabulator `virtualDom` to the largest existing list surface (Event Timeline rows / study instance list) without building full Search | **Recommended** — satisfies spirit of `02-alt` §22 without scope-creeping Search |
| **V2** | Ship a minimal Search panel + virtualized results as Phase 18 scope | Reject unless Search is explicitly re-approved |
| **V3** | Defer T-18-01-07 with accepted miss citing missing Search host | Acceptable under Option B if V1 proves unsafe |

**Default if approved without comment: V1** on Event Timeline or study browser instance list — whichever already renders large collections in templates.

**Acceptance.** Large dataset remains responsive; mouse not required for basic row focus (ties to a11y).

---

## 4. WP-18-02 — Security and accessibility

### T-18-02-01 — Input validation review (P0)

**Work.** Enumerate every HTTP/WS boundary route added since Phase 08. Verify Pydantic/boundary validation; reject unknown dangerous coercions; confirm error remediation text still present. Produce `docs/planning/phase-18-security-review.md` checklist with file:route evidence.

**Must not.** Add auth/RBAC (deferred ADR). Change public contracts without need.

### T-18-02-02 — Path containment re-verification (P0)

**Work.** Grep/audit every path-accepting route and capture I/O path since Phase 04. Re-run and extend `assert_contained` / `resolve_capture_path` tests for each new entry point (handover, reports, plugins root, settings paths).

**Acceptance.** Every path-accepting route covered by a negative traversal test.

### T-18-02-03 — Dependency vulnerability review (P0)

**Work.** Run `uv run pip-audit --strict` (CI already does). Run `npm audit` on frontend build deps. Record clean result or exceptions with rationale in `docs/planning/phase-18-dependency-audit.md`. Do **not** add Dependabot unless already desired — out of WBS unless free.

### T-18-02-04 — Secret handling review

**Work.** Audit logs, events, captures, `ConfigurationChanged`, audit log rows for secret leakage. Extend redaction denylist if gaps found. Tests for any new sensitive keys.

### T-18-02-05 — Keyboard-only operation (P0)

**Work.** Playwright (ADR-0031) scenarios: primary workflows without mouse — command palette navigation, panel switching, timeline row focus, viewer basic controls where applicable. Fail the suite if a primary workflow requires click-only affordances.

**Acceptance.** Primary workflows complete keyboard-only (`15` §12). R-20 satisfied.

### T-18-02-06 — Contrast and scalable typography

**Work.** Add high-contrast theme (`data-theme="high-contrast"` or `prefers-contrast` enhancement) consistent with existing theme switcher. Verify base typography remains ≥15px; document user scale via browser zoom (do not invent a third settings system unless runtime settings already expose theme).

### T-18-02-07 — Screen reader pass (P2)

**Work.** Manual/automated spot check of landmarks, live regions, dialog. Document honest limitations in operator or user docs — no fake "WCAG AA certified" claim.

---

## 5. WP-18-03 — Documentation

### T-18-03-01 — Glossary reconciliation (P0) — closes F-05

**Work.** Update `docs/architecture-baseline/19-glossary.md`:

| Action | Terms |
|---|---|
| Add | ring buffer, promotion, fidelity tier, condition (align with Diagnostic Condition), finding (verify), association pair, `.lpcap` |
| Correct | Study (projection per ADR-0013), Replay (ADR-0005 three meanings / two shipped), Event Store (replace with capture directory + rebuildable index per ADR-0004) |

Mark F-05 closed in `00-architecture-review-findings.md` when done. Update F-06 status text to reflect ADR-0030 partial closure + Phase 18 measurement outcome.

### T-18-03-02 — Deployment topology guide (P0)

**Work.** New `docs/guides/deployment-topologies.md`: inline proxy, destination-AE interception, standalone; reverse proxy as TLS/auth boundary (ADR-0010); `--trust-network` acknowledgment; loopback default.

### T-18-03-03 — Operator guide (P0)

**Work.** New `docs/guides/operator-guide.md`: exposure acknowledgment, network-filesystem refusal, backup targeting `app.db`, index rebuild as recovery, data dir layout (ADR-0011), read-only mode.

### T-18-03-04 — Troubleshooting guide

**Work.** New `docs/guides/troubleshooting.md` keyed to condition IDs from the condition catalogue. Link remediation text already on conditions.

### T-18-03-05 — User documentation

**Work.** Workflow-oriented docs per persona (PACS admin, integration engineer, QA, vendor support). Prefer one `docs/guides/user-workflows.md` with persona sections over five thin files.

### HIPAA/GDPR posture (Phase 18 exit, not a separate WBS row)

**Work.** New `docs/guides/privacy-and-compliance-posture.md` stating what redaction **does** and **does not** claim (ADR-0026): never "anonymize" / "de-identified" / PS3.15; object-dropping default; burned-in pixel risk; deployment-specific compliance remains the operator's responsibility. Cross-link from operator guide.

---

## 6. Explicit non-goals (do not implement)

- Authentication / RBAC / multi-user (deferred ADR)
- Prometheus exposition (ADR-0014 / Phase 17 non-goal)
- PS3.15 de-identification
- pcap import, byte-exact replay, remote collectors
- Phase 19 packaging (wheel/Docker/no-Node install verification)
- Phase 20 interop matrix
- Inventing a new `observability/` or `hardening/` slice — extend existing modules only
- Real or de-identified patient DICOM data

---

## 7. Quality gates (every task)

Per `AGENTS.md` / DoD:

```console
uv run ruff check . && uv run ruff format --check .
uv run lint-imports --no-cache
uv run basedpyright src/lumora_probe/core src/lumora_probe/shared
uv run pytest -q   # or targeted -m markers; slow/perf as appropriate
```

Frontend theme/a11y CSS changes:

```console
npm ci && npm run build:assets && npm run check:assets
```

Commit shape: one completed WBS task (or tightly coupled pair) per commit, message format:

```text
feat(perf): measure large-study browse under synthetic load
test(security): re-verify path containment on handover routes
docs(glossary): reconcile ADR vocabulary (closes F-05)
```

---

## 8. Deliverables checklist (`06-deliverables.md`)

| Deliverable | Artifact |
|---|---|
| Performance suite | `tests/test_phase18_*.py` + measurement notes in completion report |
| Security review coverage | `docs/planning/phase-18-security-review.md` + extended tests |
| Accessibility | High-contrast theme + Playwright keyboard-only primary workflows |
| Glossary reconciled | `19-glossary.md` + F-05 closed |
| Deployment / operator / troubleshooting / user docs | `docs/guides/*.md` |
| Dependency vulnerability report | `docs/planning/phase-18-dependency-audit.md` |
| HIPAA/GDPR posture | `docs/guides/privacy-and-compliance-posture.md` |
| Completion report | `docs/planning/phase-18-completion-report.md` |
| Status line | Update `CLAUDE.md` when Phase 18 accepted |

---

## 9. Open decisions (approval required)

1. **Budget posture:** Option A (ratify ADR first) vs **B (measure + document misses)** vs C (defer). Default **B**.
2. **Virtualized tables:** V1 (virtualize existing list) vs V2 (build Search) vs V3 (defer with miss). Default **V1**.
3. **Large-study instance count:** 2,000 vs 5,000 synthetic instances for T-18-01-02. Default **2,000** (thousands; cheaper CI), with optional `@pytest.mark.slow` 5,000 path.
4. **npm audit in CI:** record-only in Phase 18 audit doc vs add CI step. Default **record-only** (avoid expanding CI scope without need).

---

## 10. Suggested task commit sequence

1. `docs`: publish this plan as Approved (status flip only after human ratification)
2. `docs(glossary)`: T-18-03-01
3. `test(security)`: T-18-02-02 path containment
4. `docs(security)`: T-18-02-01 + T-18-02-04 review artifacts; fix gaps found
5. `chore(deps)`: T-18-02-03 audit document
6. `test(perf)`: T-18-01-01 … T-18-01-06 (one commit per task or bundled measure+doc)
7. `feat(web)`: T-18-01-07 virtualized list (V1)
8. `feat(a11y)`: T-18-02-05 / T-18-02-06 / T-18-02-07
9. `docs(guides)`: T-18-03-02 … T-18-03-05 + privacy posture
10. `docs(planning)`: Phase 18 completion report + `CLAUDE.md` status

---

## 11. Exit criteria mapping

| Exit criterion (`02-phase-plan.md`) | How this plan satisfies it |
|---|---|
| Every ratified budget met, or miss documented and accepted | ADR-0030 kept hard; other dims measured under Option B |
| Keyboard-only primary workflows | T-18-02-05 Playwright gate |
| Glossary carries named terms; Study/Replay/Event Store corrected | T-18-03-01 |
| Dependency scan clean or exceptions recorded | T-18-02-03 |
| HIPAA/GDPR posture states redaction claims honestly | Privacy posture guide |

**Closes.** F-05. **Advances.** F-06 (partial → measured outcome documented).
