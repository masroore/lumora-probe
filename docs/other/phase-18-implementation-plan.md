# Phase 18 — Production Hardening: Implementation Plan

**Date:** 2026-07-31
**Last verified:** 2026-07-31 against `master` at `062e760`
**Status:** Approved — implementing
**Approved:** 2026-07-31
**Selected options:** Performance Option B; Search/virtualization S1; large-study workload 2,000
instances; npm audit report-only in Phase 18
**Predecessor:** Phase 17 (Observability) — complete
**Milestone:** M13 — Release Candidate (`docs/planning/04-milestones.md`)
**Governing docs:** `docs/planning/02-phase-plan.md` §Phase 18,
`docs/planning/01-work-breakdown-structure.md` C-18,
`docs/planning/06-deliverables.md` §Phase 18,
`docs/architecture-baseline/13-testing-strategy.md` §12–13,
`docs/architecture-baseline/15-ui-ux-guidelines.md` §12–16,
`docs/architecture-baseline/12-security-architecture.md`, ADR-0004, ADR-0005, ADR-0008,
ADR-0009, ADR-0010, ADR-0011, ADR-0013, ADR-0018, ADR-0019, ADR-0022, ADR-0023,
ADR-0025, ADR-0026, ADR-0030, ADR-0031, ADR-0033

---

## 0. Verification corrections

| Planning claim or draft assumption | Verified position at Phase 17 exit |
|---|---|
| Phase 11 ratified startup, large-study, throughput, memory, replay, and concurrent-client budgets | **Incorrect.** ADR-0030 ratifies capture event/PDU cardinality, ring retention/cap, and durable-writer behavior only. The six Phase 18 assessment dimensions still lack release thresholds. |
| UI responsiveness under 100 ms is merely untested/provisional | **Incomplete.** It is an approved planning target and `tests/test_phase09_websocket.py` enforces a 5,000-event server-side flush under 100 ms. ADR-0031's browser test verifies no viewer round trip but explicitly calls its timing a smoke bound. ADR-0030 does not ratify a browser latency gate. |
| F-06 is stale because Phase 11 closed it | **Incorrect.** F-06 remains legitimately **OPEN**: ADR-0030 addresses capture volume/retention but not all dimensions named by F-06. Under budget Option B, Phase 18 adds evidence but does not close F-06. |
| A new performance ADR would be ADR-0032 | **Stale.** ADR-0033 already exists. Use the next available ADR number at creation time; do not reuse an abandoned number in this plan. |
| T-18-01-07 can be satisfied by adding Tabulator to any large list | **Incorrect without explicit rescoping.** The WBS declares T-13-04-08 Search as its dependency. Search was deferred from Phase 13 to Phase 14 and never delivered. Retargeting an arbitrary `<ol>`/`<ul>` does not satisfy the declared Search/table dependency. |
| No search/table host exists | **Verified with qualification.** The workspace has an Event Timeline `<ol>`, a study-object `<ul>`, and a metadata `<table>`, but no global Search panel or virtualized result table. Tabulator is vendored and unused by application source. |
| `12-security-architecture.md` §8 is input validation and §6 is secret handling | **Incorrect WBS cross-references.** API input validation is §12; secrets management is §8. Sections §6–7 are authentication/authorization and are superseded for v1 by ADR-0009. |
| Startup readiness is `/api/v1/ready` | **Incorrect.** The production route is `GET /api/v1/health/ready`. |
| `@pytest.mark.slow` makes a test opt-in | **Incorrect in the current harness.** The marker classifies tests but `uv run pytest -q` still collects and runs them. Only `e2e` has an environment guard (`LUMORA_E2E=1`). |
| `uv run pip-audit --strict` matches CI | **Incomplete.** CI first exports all locked groups, then runs `uv run pip-audit --strict -r audit-requirements.txt`. Phase 18 must reproduce that audited input. |
| Network filesystems are categorically refused | **Too broad.** SQLite paths are refused on detected network filesystems. Capture directories may live on network shares per ADR-0011. |
| Existing operator documentation includes `docs/capture-engine.md` under `docs/guides/` | **Incorrect location.** `docs/guides/vendor-handover.md` and root-level `docs/capture-engine.md` exist; deployment, operator, troubleshooting, persona workflow, and compliance-posture guides do not. |

---

## 1. Pre-phase decision: performance budget posture

This decision blocks WP-18-01 performance work only. Security, accessibility inventory, and
documentation may proceed independently after the overall plan is approved.

### Option A — Ratify additional release budgets

Measure representative synthetic workloads, then approve a new ADR or explicit ADR-0030
extension before turning new values into release gates.

**Result:** Phase 18 may report pass/fail against approved thresholds and may close F-06 if the
new ADR covers every unresolved dimension.

**Cost:** Calibration and ADR review precede performance acceptance.

### Option B — Preserve ratified gates; measure unresolved dimensions (recommended)

1. Keep ADR-0030 thresholds as hard release gates through existing Phase 11 coverage.
2. Preserve the existing 5,000-event/<100 ms server-side UI flush gate and the browser
   no-round-trip assertion. Label their scopes accurately; do not present either as a ratified
   end-to-end browser latency guarantee.
3. Measure startup, large-study handling, event throughput, memory, replay, and concurrent
   clients using the workload matrix below.
4. Report each unratified dimension as **measured**, **limited**, or **not verified**. Do not call a
   result a pass/fail or an "accepted miss" against a threshold that was never approved.
5. A miss against an ADR-0030 gate requires an approved ADR update or explicitly versioned
   exception before Phase 18 acceptance. A completion-report note alone cannot override an ADR.
6. Do not add hardware-sensitive hard CI thresholds without an ADR.

**Result:** Satisfies `13-testing-strategy.md` §12's assessment requirement without inventing
release guarantees. F-06 remains OPEN, with Phase 18 evidence linked from the finding.

### Option C — Defer unresolved measurements

**Rejected.** The Phase 18 work statement and testing strategy require assessment of all six
named dimensions. Documentation without measurement is insufficient.

**Default on plan approval:** Option B.

### Measurement workload matrix under Option B

Every row records OS, CPU class, RAM, Python version, commit, workload seed/count, run count, and
measurement method in `docs/planning/phase-18-performance-report.md`.

| Dimension | Required workload | Release interpretation |
|---|---|---|
| Startup | Five isolated `lumora serve` subprocess starts with a fresh temporary data root; parent process measures monotonic duration until `GET /api/v1/health/ready` succeeds | Evidence only unless Option A ratifies a threshold |
| Large study | Deterministic projection/API browse of **2,000 synthetic instances** using project UID namespace; no pixel decode | Evidence plus correctness assertions; 2,000 is workload identity, not a latency gate |
| Event throughput | 5,000 canonical domain events through bus, capture subscriber, and UI governor; PDU trace remains outside the bus | Existing <100 ms governor scope retained; other timings evidence only |
| Memory | At least three ring-fill/eviction cycles at a reduced deterministic cap; record RSS or documented platform substitute and retained-byte trend | Ring byte cap is hard per ADR-0030; process-memory trend is evidence only |
| Replay | 500 deterministic `ProtocolReplayDataset` records with injected sleeper/transport for orchestration cost; optional local loopback target reported separately | Timing fidelity remains a hard correctness assertion; elapsed performance is evidence only |
| Concurrent clients | Incremental local matrix of 1, 4, and 8 `/ws/ui` clients plus one `/api/v1/events/stream` client | Drop/error accounting is hard correctness; client count/latency is evidence only |
| UI interaction | Existing 5,000-event governor test plus browser measurements for keyboard workflows and large-result navigation | Existing scoped gate retained; end-to-end measurements are not ratified under Option B |

The planning phrase "Enhanced MR — thousands of instances" is internally imprecise: Enhanced MR
objects are commonly multi-frame. Phase 18 will call this a **large synthetic study projection**
with 2,000 instances. It will not claim modality-faithful Enhanced MR performance unless a separate
multi-frame fixture is explicitly added and identified.

---

## 2. Current state inventory

| Area | Verified location | Status |
|---|---|---|
| Ratified capture budgets | `docs/adr/ADR-0030-ratified-performance-budgets.md`, `tests/test_phase11_budgets.py` | Exists; capture volume/retention only |
| UI governor budget | `tests/test_phase09_websocket.py` | Exists; server-side 5,000-event flush only |
| Browser e2e harness | `tests/test_phase13_viewer_e2e.py`, `tests/conftest.py` | Exists; opt-in, no-round-trip smoke assertion |
| Production bootstrap | `src/lumora_probe/bootstrap.py`, `src/lumora_probe/cli.py` | Exists; `build_production_app()`, `lumora serve` |
| Readiness route | `src/lumora_probe/web/health_routes.py` | Exists; `/api/v1/health/ready` |
| Study browser projection | `src/lumora_probe/studies/service.py`, `src/lumora_probe/web/study_routes.py` | Exists; JSON/provider surface and workspace study-object list |
| Replay timing seams | `src/lumora_probe/replay/`, `tests/test_phase12_*.py` | Exists; injected sleeper/transport, no test sleep required |
| Path containment | `src/lumora_probe/core/paths.py` | Exists |
| HTTP/WS security | `src/lumora_probe/web/security.py`, Phase 08/09 tests | Exists |
| Secret redaction | `src/lumora_probe/core/logging.py`, `src/lumora_probe/settings/runtime.py`, `src/lumora_probe/reports/redaction.py` | Exists; requires review coverage |
| Python dependency audit | `.github/workflows/ci.yml` | Exists; locked all-groups export + `pip-audit --strict` |
| npm dependency audit | `package-lock.json` | Manual only; no CI audit step |
| Workspace semantics | `src/lumora_probe/web/templates/workspace.html`, `assets/source/command-palette.js` | ARIA/focus foundations exist |
| Runtime theme setting | `src/lumora_probe/settings/runtime.py` | Exists; workspace currently hard-codes `system` and binary light/dark toggle |
| High-contrast theme | `assets/source/app.css` | Missing |
| Keyboard-only browser gate | Playwright suite | Specific workflow coverage missing |
| Virtualized Search results | Tabulator vendor assets | Dependency vendored; Search host and application integration missing |
| Glossary | `docs/architecture-baseline/19-glossary.md` | Partial; F-05 remains open |
| Existing operator-facing docs | `docs/guides/vendor-handover.md`, `docs/capture-engine.md` | Partial |
| HIPAA/GDPR posture | — | Missing; ADR-0026 is the governing technical decision |

---

## 3. Work package overview

| WP | Name | Tasks | Dependency notes |
|---|---|---|---|
| WP-18-01 | Performance | T-18-01-01 … T-18-01-07 | Budget posture first; T-18-01-07 also requires Search dependency resolution |
| WP-18-02 | Security and accessibility | T-18-02-01 … T-18-02-07 | Security inventory can run in parallel; a11y follows final UI scope |
| WP-18-03 | Documentation | T-18-03-01 … T-18-03-05 plus required compliance posture | Glossary can start early; operator docs consume measured limitations |

Recommended flow:

1. Ratify this plan and Option B.
2. Start T-18-03-01 and T-18-02-01/02/03/04 in parallel.
3. Run T-18-01-01 … 06 measurement work.
4. Restore Search prerequisite, then complete T-18-01-07.
5. Complete accessibility against the final UI.
6. Write operator/user/compliance docs from verified behavior and measurement results.
7. Run all acceptance gates and publish the completion report.

---

## 4. WP-18-01 — Performance

### T-18-01-01 — Startup time

**Work.** Measure the real process boundary: spawn `lumora serve` on loopback with a fresh temporary
`LUMORA_DATA_DIR`, poll `GET /api/v1/health/ready`, record monotonic elapsed duration, then terminate
cleanly. Also record `build_production_app()` duration separately so composition cost and server
startup are not conflated.

**Constraints.** Duration uses a monotonic source, never wall-clock subtraction. Poll readiness;
do not add a fixed test sleep. Preserve the non-loopback exposure gate.

**Acceptance.** Five-run evidence and environment identity recorded. Startup failures/timeouts fail
correctness. Elapsed values remain informational under Option B.

**Planned coverage.** `tests/test_phase18_startup.py` plus performance report.

### T-18-01-02 — Large study handling (P0)

**Work.** Build 2,000 minimal synthetic instance projections using deterministic IDs and the approved
DICOM UID namespace. Exercise projection persistence, `StudyBrowserService.browser()`, and
`GET /api/v1/studies/{study_uid}/browser`. Verify provenance/partial-state semantics and that the
path does not decode pixel data.

**Constraints.** No real or de-identified patient data. Do not claim clinical viewer, modality-faithful
Enhanced MR, or pixel-render performance. Avoid committing thousands of generated fixtures when a
deterministic generator can create the workload in a temporary directory/database.

**Acceptance.** Correct 2,000-instance result, explicit failure behavior, elapsed and memory evidence.
The `slow` marker may classify the test but does not make it opt-in; the workload must remain viable
in the normal full suite unless the test harness is separately changed and documented.

**Planned coverage.** `tests/test_phase18_large_study.py`.

### T-18-01-03 — Event throughput under load (P0)

**Work.** Extend the existing 5,000-domain-event workload through the real event bus, capture
subscriber, and coalescing governor. Keep PDU trace records in `pdus.jsonl`; never publish them as
domain events to improve a metric. Reuse existing drop-accounting adversarial patterns.

**Acceptance.** Durable capture events are not silently dropped; any bounded UI-channel loss equals
reported `EventsDropped`/sequence evidence; existing <100 ms governor test remains green. Additional
bus/capture timings are recorded, not converted to gates under Option B.

**Planned coverage.** Extend existing component tests or add `tests/test_phase18_throughput.py` only
where the existing Phase 09/11 coverage cannot express the combined path.

### T-18-01-04 — Memory profile

**Work.** Run at least three deterministic ring-fill/eviction cycles. Record process RSS where the
platform exposes it without a new dependency; otherwise document the substitute (for example,
Python allocation trend) and its limitation. Measure after comparable cycle boundaries.

**Acceptance.** ADR-0030 retained-byte cap/retention behavior passes. Report whether process memory
stabilizes, trends upward, or cannot be compared reliably. Do not add a noisy cross-platform RSS
hard assertion under Option B.

**Planned coverage.** Component correctness test plus performance-report measurements.

### T-18-01-05 — Replay performance

**Work.** Separate deterministic replay-orchestration cost from network behavior:

1. Replay 500 `ProtocolReplayDataset` records through the injected sleeper and transport; preserve
   reconstructed-delay assertions without actually waiting for captured delays.
2. Optionally run the same synthetic workload against a local pynetdicom loopback target and report
   it as environment-specific evidence.

Do not make Phase 20 interoperability implementations a Phase 18 dependency. Do not add capture
input assembly as hidden scope if the current public runtime still requires explicit replay records.

**Acceptance.** Ordering, fidelity refusal, exclusivity, cancellation, and timing reconstruction
remain green. Elapsed orchestration/loopback results are recorded under distinct labels.

**Planned coverage.** Extend Phase 12 replay tests or add `tests/test_phase18_replay_performance.py`.

### T-18-01-06 — Concurrent client load

**Work.** Start the local application and exercise 1, 4, then 8 subscribed `/ws/ui` clients while one
`/api/v1/events/stream` client consumes canonical envelopes. Publish a deterministic burst at each
level.

**Acceptance.** Connections either succeed or fail explicitly; no silent disconnect; mounted-view
filtering remains correct; drops and sequence gaps reconcile. Record delivery/flush timing and the
highest completed matrix row. Counts are workload identity, not a release capacity claim.

**Planned coverage.** `tests/test_phase18_concurrent_clients.py`.

### T-18-01-07 — Virtualized tables and missing Search prerequisite

The declared dependency T-13-04-08 was not delivered. Budget Option B does not authorize a feature
scope miss; its "measured/limited" vocabulary applies only to unratified performance dimensions.

| Resolution | Action | Verdict |
|---|---|---|
| **S1** | Restore a minimal T-13-04-08 Search panel over existing studies/series/instances/events/logs contracts, then virtualize its result table with the already-vendored Tabulator assets | **Recommended/default**; satisfies the declared dependency and task intent |
| **S2** | Explicitly defer Search and T-18-01-07 together, update phase acceptance/dependency records, and record the release scope reduction | Allowed only through separate human approval; not an Option B performance miss |
| **S3** | Apply Tabulator to Event Timeline or the study-object list and claim T-18-01-07 complete | **Rejected** unless the WBS task is explicitly rescoped; current surfaces are lists, not the missing Search result table |

**S1 scope control.** Compose existing read contracts; do not introduce a durable global Search
aggregate, new search index, or cross-slice imports. Incremental/paginated result retrieval must
avoid rendering the full 2,000-row workload server-side before virtualization.

**Acceptance.** Large Search results remain responsive; result count/order/filter semantics are
correct; keyboard row navigation, focus visibility, activation, and screen-reader labeling pass the
Phase 18 accessibility checks. Vendored assets remain offline and committed per ADR-0025.

---

## 5. WP-18-02 — Security and accessibility

### T-18-02-01 — Input validation review (P0)

**Work.** Inventory every public HTTP and WebSocket boundary, not only routes added after Phase 08.
Use generated OpenAPI/AsyncAPI plus route registration to cover path/query/header/body fields,
WebSocket subscription messages, size/count limits, coercion, structured errors, and remediation.
Record file:route evidence in `docs/planning/phase-18-security-review.md`.

The controlling baseline citation is `12-security-architecture.md` §12 (API Security), not §8.
Authentication/authorization rows are recorded as v1-not-applicable under ADR-0009; plugin isolation
is recorded as trusted in-process under ADR-0021 rather than falsely claimed.

**Acceptance.** Every public route/socket is classified and reviewed. Any contract correction
regenerates OpenAPI/AsyncAPI artifacts and preserves unknown event fields where required.

### T-18-02-02 — Path containment re-verification (P0)

**Work.** Inventory externally influenced filesystem sinks separately from startup-configured roots.
Cover capture IDs/paths, report and handover artifacts, read-only capture roots, plugin CLI install
paths, and any setting that ultimately forms a path. Verify UUIDv7 validation where required,
`resolve()`, containment, symlink escape behavior, and explicit error remediation.

Do not describe plugin root or settings paths as HTTP routes when they are configuration/CLI
boundaries. Verify SQLite network-filesystem refusal separately from allowed capture shares.

**Acceptance.** Every externally influenced filesystem sink has a negative traversal/escape test at
the boundary that owns it. Existing shared helpers are reused; no parallel containment utility.

### T-18-02-03 — Dependency vulnerability review (P0)

**Work.** Reproduce CI's Python audit input:

```console
uv export --format requirements.txt --all-groups --no-emit-project --output-file audit-requirements.txt
uv run pip-audit --strict -r audit-requirements.txt
npm audit
```

Remove the temporary exported requirements file after recording tool versions/results. Distinguish
runtime, dev-only, and build-only findings. Record clean results or reviewed exceptions with package,
advisory, exposure, mitigation, owner, and expiry/review date in
`docs/planning/phase-18-dependency-audit.md`.

**CI decision.** Python remains a hard CI audit. npm remains report-only by default for Phase 18;
adding a blocking npm CI step requires explicit approval based on actual findings, not a generic
hardening preference.

### T-18-02-04 — Secret handling review

**Work.** Review startup/runtime settings, structured logs, error contexts, event payloads,
`ConfigurationChanged`, audit rows, reports, plugin diagnostics, and handover artifacts for API
keys, tokens, passwords, certificates/private keys, or future credential-shaped fields. Extend the
central redaction policy and tests when gaps exist.

**Boundary.** DICOM evidence may intentionally contain PHI; this task does not pretend captures are
PHI-free. Secret leakage and ADR-0026 redaction/compliance posture are separate concerns.

**Acceptance.** No identified secret value reaches logs, events, reports, audit output, or generated
error context. Redacted keys retain enough name/source context for diagnosis.

### T-18-02-05 — Keyboard-only operation (P0)

**Work.** Extend the ADR-0031 Playwright gate with mouse-free scenarios for:

- opening, navigating, activating, and closing the command palette with focus restoration;
- moving between workspace regions/panels and operating collapse controls;
- navigating and activating Search results if S1 is approved;
- focusing/jumping through Event Timeline rows;
- operating applicable viewer controls, cine, and fullscreen;
- selecting the high-contrast theme and returning focus predictably.

Tests use keyboard input only after initial page navigation. Server readiness is polled, not handled
with a fixed sleep.

**Acceptance.** Primary workflows complete without mouse APIs; focus remains visible and ordered;
no keyboard trap; dialogs return focus to the invoker.

**Gate.** `LUMORA_E2E=1 uv run pytest -m e2e -q` after Chromium installation.

### T-18-02-06 — Contrast and scalable typography

**Work.** Extend the existing runtime `theme` setting and workspace theme application with an
explicit high-contrast option. Preserve light/dark/system behavior and support `prefers-contrast`
where available. Replace the binary-only toggle behavior with a control that can reach every
supported value.

Verify primary workflows at 200% browser zoom/text scaling: content remains operable, focus is not
obscured, critical text is not clipped, and horizontal scrolling is limited to genuinely tabular
regions. Check text, controls, focus rings, statuses, charts, and severity colors; color alone cannot
carry meaning.

**Acceptance.** High-contrast theme is selectable/persisted through the existing setting path;
contrast evidence and 200% scaling screenshots/results are recorded. A 15 px root declaration alone
does not satisfy scalable typography.

### T-18-02-07 — Screen reader pass (P2)

**Work.** Run semantic browser assertions plus at least one documented desktop screen-reader/browser
pairing on the reference environment. Check landmarks, heading order, live-region noise, dialog
name/description, table/grid semantics, result counts, dropped-event announcements, and control
state (`aria-expanded`, `aria-selected`, `aria-pressed`).

**Acceptance.** Blocking issues are fixed or explicitly documented with workflow, impact, and
workaround. Do not claim WCAG certification or universal screen-reader support.

**Artifact.** `docs/planning/phase-18-accessibility-review.md`.

---

## 6. WP-18-03 — Documentation

### T-18-03-01 — Glossary reconciliation (P0) — closes F-05

Update `docs/architecture-baseline/19-glossary.md` against accepted ADR vocabulary:

| Action | Terms |
|---|---|
| Add/normalize | ring buffer, promotion, fidelity tier, Condition (with Diagnostic Condition alias handled explicitly), Finding, association pair, `.lpcap` |
| Correct | Study/Series/Instance as capture-derived projections (ADR-0013); Replay as three meanings/two shipped modes (ADR-0005); Event Store replaced by capture directory/canonical event log plus rebuildable index (ADR-0004) |
| Remove ambiguity | Capture vs `.lpcap`; protocol trace vs domain event; redaction vs de-identification |

Mark F-05 CLOSED with the resulting definitions. Under Option B, append Phase 18 measurement evidence
to F-06 but keep F-06 OPEN. Close F-06 only if Option A ratifies all unresolved targets.

### T-18-03-02 — Deployment topology guide (P0)

Create `docs/guides/deployment-topologies.md` covering inline proxy, destination-AE interception,
and standalone operation. Distinguish implemented/supported behavior from conceptual future
variants. State loopback default, `--trust-network` acknowledgment, no-auth v1 posture, and reverse
proxy responsibility for TLS/authentication without implying built-in TLS or RBAC.

### T-18-03-03 — Operator guide (P0)

Create `docs/guides/operator-guide.md` covering startup/config source precedence, exposure gate,
read-only mode, data-root layout, health/readiness, shutdown/recovery, and backup.

Required precision:

- SQLite databases are refused on detected network filesystems; capture roots may be network shares.
- `index.db` is derived and rebuildable.
- `app.db` is the only non-rebuildable database file and must be backed up.
- Capture directories are authoritative evidence and require preservation/backup according to the
  operator's retention obligations; "back up app.db" must not imply evidence needs no backup.

Cross-link `docs/capture-engine.md` and `docs/guides/vendor-handover.md` rather than duplicating them.

### T-18-03-04 — Troubleshooting guide

Create `docs/guides/troubleshooting.md`, keyed to stable IDs in
`docs/condition-catalogue-v1.md`/generated catalogue. Link existing remediation text. Add operational
sections for startup/config errors, readiness failures, data-root/network-filesystem refusal,
rebuild recovery, dropped UI events, replay refusal, and dependency/audit exceptions. Do not invent
condition IDs for operational errors that are not diagnostic conditions.

### T-18-03-05 — User documentation

Create `docs/guides/user-workflows.md` with task-oriented sections for PACS administrator,
integration engineer, QA engineer, and vendor support. Cover capture investigation, study
provenance/partial-state interpretation, timeline/conditions/findings, replay safety, reports, and
safe handover. Keep operator deployment procedures in the operator guide.

### Required HIPAA/GDPR posture document

Create `docs/guides/privacy-and-compliance-posture.md` from ADR-0026 and Security Architecture §17.
State:

- captures may contain PHI;
- "redact" is partial redaction, never an anonymization/de-identification claim;
- no PS3.15 conformance claim;
- object-dropping/events fidelity is the safe default handover;
- private tags, free text, structured content, and burned-in pixels remain risks;
- encryption, access control, retention, lawful basis, breach response, and jurisdiction-specific
  compliance are deployment responsibilities;
- Lumora Probe documentation is not a compliance certification.

Cross-link from operator and vendor-handover guides.

---

## 7. Explicit non-goals

- Authentication, RBAC, identities, sessions, or multi-user semantics (ADR-0009 deferred work)
- Prometheus exposition or a core Prometheus dependency
- PS3.15 de-identification or an anonymization claim
- pcap import, byte-exact/mock-peer replay, or remote collectors
- New global Search aggregate/index beyond the minimum existing-contract Search prerequisite
- Phase 19 wheel/Docker/no-Node installation work
- Phase 20 DCMTK/dcm4che/Orthanc interoperability matrix
- New `observability/`, `hardening/`, or performance domain slice
- Host CPU/storage telemetry without an approved source/lifecycle contract
- Real or de-identified patient DICOM data
- Changing ADR decisions through a plan or code comment

---

## 8. Quality and acceptance gates

Targeted tests may be used during development but do not replace the final full gate.

### Python and architecture

```console
uv run ruff check .
uv run ruff format --check .
uv run lint-imports --no-cache
uv run basedpyright src/lumora_probe/core src/lumora_probe/shared
uv run pytest -q
```

### Browser accessibility

```console
uv run playwright install chromium
LUMORA_E2E=1 uv run pytest -m e2e -q
```

### Frontend assets

```console
npm ci
npm run check:assets
```

`npm run check:assets` already rebuilds assets before checking drift; do not require a redundant
preceding `npm run build:assets` in the gate.

### Dependency audit

```console
uv export --format requirements.txt --all-groups --no-emit-project --output-file audit-requirements.txt
uv run pip-audit --strict -r audit-requirements.txt
npm audit
rm audit-requirements.txt
```

### Generated contracts and documentation

- Regenerate OpenAPI/AsyncAPI/event/condition artifacts if their source contracts change.
- Update the glossary for any newly introduced domain term.
- Run `git diff --check` and verify every new relative documentation link/path.
- Run `npm run check:assets` after any source asset or vendor-manifest change.
- Use synthetic DICOM only.

---

## 9. Deliverables

| Deliverable | Required artifact/evidence |
|---|---|
| Performance assessment | `tests/test_phase18_*.py` or justified extensions to existing suites; `docs/planning/phase-18-performance-report.md` |
| Ratified capture gates | Existing ADR-0030 tests remain green; any exception requires ADR action |
| Security review | `docs/planning/phase-18-security-review.md` plus gap tests/fixes |
| Dependency review | `docs/planning/phase-18-dependency-audit.md` |
| Accessibility | Browser tests plus `docs/planning/phase-18-accessibility-review.md` |
| Virtualized tables | Search prerequisite and virtualized result table, unless separately approved deferral S2 |
| Glossary | Reconciled `docs/architecture-baseline/19-glossary.md`; F-05 closed |
| Operator docs | Deployment topology, operator, troubleshooting, and persona workflow guides |
| Compliance posture | `docs/guides/privacy-and-compliance-posture.md` |
| Completion | `docs/planning/phase-18-completion-report.md`; `CLAUDE.md` status updated only after acceptance |

---

## 10. Approval decisions

1. **Performance posture:** Option A vs **Option B (default/recommended)**. Option C rejected.
2. **Search/virtualization dependency:** **S1 restore Search prerequisite (default/recommended)** vs
   S2 explicit joint deferral. S3 arbitrary-list retarget rejected.
3. **Large-study automated workload:** **2,000 instances (default)**. A 5,000-instance local run may
   add evidence but is not required and is not made opt-in merely by adding `slow`.
4. **npm audit CI:** **Report-only in Phase 18 (default)** vs blocking CI after findings are reviewed.

Approval without edits selects the defaults above. Approval does not waive ADR or task-level DoD
gates.

---

## 11. Suggested commit sequence after approval

1. `docs(planning)`: mark this plan Approved and record selected options
2. `docs(glossary)`: T-18-03-01; close F-05, retain/update F-06 as required
3. `docs(security)`: boundary/path/secret inventories and review artifacts
4. `test(security)`: close verified validation/containment/redaction gaps
5. `chore(deps)`: dependency audit artifact and approved remediations
6. `test(perf)`: T-18-01-01 … 06, with report updates alongside measurements
7. `feat(search)`: recover T-13-04-08 minimum prerequisite if S1 selected
8. `feat(web)`: T-18-01-07 virtualized Search results
9. `feat(a11y)`: T-18-02-05 … 07 and accessibility review
10. `docs(guides)`: T-18-03-02 … 05 plus compliance posture
11. `docs(planning)`: completion report and final status update after all gates pass

Each commit should represent one WBS task or a tightly coupled code+test+artifact unit. Do not split a
measurement from the report needed to interpret it.

---

## 12. Exit-criterion mapping

| Phase 18 exit criterion | Evidence required by this plan |
|---|---|
| Every ratified budget met, or miss documented and accepted | ADR-0030 gates remain green. Any miss needs approved ADR update/versioned exception; unratified dimensions are measured without false pass/fail labels. |
| Performance dimensions assessed | Workload matrix executed and `phase-18-performance-report.md` records environment, method, results, and limitations. |
| Keyboard-only primary workflows | T-18-02-05 Playwright scenarios pass with `LUMORA_E2E=1`. |
| Contrast and scalable typography | Explicit high-contrast theme plus 200% scaling/contrast evidence. |
| Glossary reconciled | T-18-03-01 definitions merged; F-05 CLOSED. |
| Dependency scan clean or exceptions recorded | Locked Python audit and npm audit documented with reviewed exceptions. |
| HIPAA/GDPR posture honest | Privacy/compliance guide states ADR-0026 limits and deployment responsibilities. |
| WBS work complete | Search prerequisite + virtualization delivered under S1, or S2 separately approved and recorded; Option B alone cannot waive the task. |

**Finding outcome:** F-05 closes. Under default Option B, F-06 remains OPEN but gains Phase 18
measurement evidence and an explicit list of still-unratified dimensions. Under Option A, F-06 may
close only when the accepted ADR covers the unresolved dimensions.
