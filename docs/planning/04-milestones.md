# 04 — Milestones

> **Project:** Lumora Probe
>
> **Document:** Milestones
>
> **Status:** Planning Baseline
>
> **Audience:** Engineering, Architects, Product, QA

---

# 1. Purpose

Fourteen milestones, each a **verifiable state of the system** rather than a date. A
milestone is reached when its criteria are demonstrably met — not when the work feels
finished.

Milestones exist so progress is legible without reading 310 tasks, and so a slip is
detected at a boundary rather than at release.

---

# 2. Milestone summary

| ID | Milestone | Phase | Nature |
|----|-----------|-------|--------|
| M1 | Architecture Frozen | 01 | Governance |
| M2 | Repository Ready | 02 | Structural |
| M3 | Pipeline Green | 03 | Process |
| M4 | Core Complete | 05 | Platform |
| M5 | Storage Complete | 06 | Platform |
| M6 | Event Backbone Complete | 07 | Platform |
| M7 | API Complete | 09 | Interface |
| M8 | Traffic Observable | 10 | **Product proof** |
| M9 | Capture Operational | 11 | **Product proof** |
| M10 | Replay Operational | 12 | Capability |
| M11 | Viewer Operational | 13 | Capability |
| M12 | Beta Ready | 15 | Release track |
| M13 | Release Candidate | 17 | Release track |
| M14 | Production Ready | 20 | Release |

M8 and M9 are the two that matter most. Everything before them is infrastructure that
could in principle serve a different product; M8 is the first moment Lumora Probe does
the thing it exists to do, and M9 is the first moment that evidence survives.

---

# 3. Milestone criteria

## M1 — Architecture Frozen (Phase 01)

- Architecture review published; all 21 baseline documents and 26 ADRs assessed.
- ADR-0027 accepted — the PRD ambiguity that sits above the ADR layer in Charter §12 is
  resolved before any requirement is traced.
- ADR-0030 drafted with provisional non-functional budgets.
- Phase numbering reconciled; the three drifted ADR citations recorded.
- Gap register carried into the WBS; no High finding without an owning phase.

**Evidence:** `00-architecture-review-findings.md`, ADR-0027, ADR-0030 draft.

## M2 — Repository Ready (Phase 02)

- Nine ADR-0012 slices exist with their five-file structure.
- All six import-linter contracts active.
- Each contract **proven to fail** on a deliberate violation (T-02-02-02).
- `uv sync` succeeds from a clean checkout.

**Evidence:** passing boundary-violation test suite.

## M3 — Pipeline Green (Phase 03)

- CI runs format, lint, static analysis, tests, coverage and dependency scan, each
  actually gating.
- Synthetic DICOM fixture generator produces a reviewable study; **no real patient data in
  the repository, de-identified or otherwise**.
- pynetdicom threading spike answered and written up.
- Provisional budgets recorded with a Phase 11 ratification task.

**Evidence:** green CI run; spike report; fixture output.

## M4 — Core Complete (Phase 05)

- Two-tier config with per-setting provenance; env-pinned settings render locked.
- Startup refuses non-loopback bind without acknowledgment, and explains why.
- Path traversal rejected by test; network filesystem refused for the databases.
- Lifecycle manager starts and stops heterogeneous services in reverse order.
- Domain model is plain Python; `Clock` and `IdGenerator` injected, with `time.`/`uuid.`
  banned outside `core/` by contract.
- Both halves of `Clock` independently freezable.

**Evidence:** contract checks; startup refusal tests; traversal test.

## M5 — Storage Complete (Phase 06)

- `index.db` and `app.db` physically split.
- Index provably rebuildable: delete, rebuild, byte-compare the projection.
- Capture directory format complete; `.lpcap` packs and unpacks with a version marker.
- Dropping a `.lpcap` into the captures folder makes it appear.
- Digest verification detects a tampered object.
- ADR-0029 accepted; cascade behaviour tested for a study spanning three captures.

**Evidence:** rebuild byte-comparison; tamper-detection test.

## M6 — Event Backbone Complete (Phase 07)

- Bus is loop-owned with exactly one thread boundary.
- `sequence` gap-free under load; a saturated UI channel produces a gap **matching** the
  `EventsDropped` count.
- Capture path never drops, verified under saturation.
- `origin` absent is a validation error.
- Unknown future fields round-trip without loss.
- Versioned event catalog generated from code and published.

**Evidence:** adversarial ordering and drop tests (T-07-02-08); published catalog.

## M7 — API Complete (Phase 09)

- `/api/v1` covers the `08` §6 resources with consistent errors and pagination limits.
- Read-only mode blocks every mutating route through a single seam.
- Foreign `Host` rejected; cross-origin state change rejected; WebSocket handshake
  origin-checked.
- Both stream endpoints served from one bus subscription through the coalescing governor.
- One set of Jinja partials serves first paint and live update.
- 5,000-event burst stays within the 100 ms UI budget.
- CLI operates against the API; OpenAPI published.

**Evidence:** burst budget test; security rejection tests; template audit showing no
duplicated panel logic.

## M8 — Traffic Observable (Phase 10)

The first product proof. Probe sits in the path and explains what happened.

- C-STORE observed end to end against real pynetdicom.
- Relay passes unrecognized DIMSE through byte-faithfully, recorded, never aborted.
- Malformed traffic relayed **without repair**, proven by byte comparison.
- Per-leg timings attributed separately across downstream, Probe hop and upstream.
- C-MOVE relayed with progress responses recorded.
- Domain event volume per instance within ADR-0014's bound; PDU records never on the bus.
- Every association audit-logged with calling AE and source IP.

**Evidence:** loopback component tests; byte-fidelity test; bus-volume assertion.

## M9 — Capture Operational (Phase 11)

The second product proof. Evidence survives, including the evidence nobody knew to record.

- Ring buffer enabled by default, holding its cap under sustained traffic.
- Retroactive promotion produces a sealed capture from a past window.
- Mid-association promotion marked `partial` with incomplete aggregates named.
- Kill mid-capture: torn trailing line discarded, capture marked `Interrupted`, index
  rebuilt.
- SIGTERM drains; last events persisted.
- Non-functional budgets ratified against real traffic and promoted to release gates.

**Evidence:** kill-test; drain-test; ratified ADR-0030.

## M10 — Replay Operational (Phase 12)

- Event replay reproduces a capture's stream; golden fixture comparison is byte-identical.
- Protocol replay sends to a configured target, dry-run by default.
- A capture at `fidelity: events` **refuses** protocol replay and names the missing stream.
- Non-allowlisted target refused.
- Restart transitions a `running` replay to `Interrupted`; nothing auto-resumes.
- Cancellation reports instances sent **and confirmed**.
- One protocol replay at a time, refused not queued.

**Evidence:** golden fixture regression; guardrail refusal tests; restart sweep test.

## M11 — Viewer Operational (Phase 13)

- Server decodes; Cornerstone renders through the custom loader.
- Decode duration appears in a capture and a report — reproducible off the originating
  machine.
- A study spanning three captures never renders as whole.
- Duplicate SOP Instance UID with differing digests reported with both digests.
- Ring-buffer-backed instances show retention state and offer promotion.
- W/L drag within 100 ms with no round trip.
- Undecodable syntax reports why — decode failure distinguishable from a rendering gap.
- Folder import creates a synthetic capture that protocol replay refuses.

**Evidence:** decode-timing in an exported report; partial-study UI test; duplicate-UID
finding.

## M12 — Beta Ready (Phase 15)

- Analysis separates observed conditions from inferred findings; nothing inferred appears
  in `events.jsonl`.
- Delete `analysis/`, re-run, obtain identical findings.
- Every finding cites resolvable sequence numbers, linked in the UI.
- Seed rule set covers the `01` §3 catalogue.
- Reports carry the rule-set version.
- Default export drops objects; pixel-bearing export is opt-in.
- Redaction outputs a new capture with consistent UID remapping and honest warnings.
- No string anywhere claims anonymization or PS3.15 conformance.

**Evidence:** purity test; terminology audit; default-export inspection.

## M13 — Release Candidate (Phase 17)

- Seed rules run on the **public** SDK with no privileged access.
- A raising plugin is contained and disabled; a slow plugin warns then auto-disables.
- No API route installs a plugin.
- Metrics derived from the event stream; a metric and its event count agree by
  construction.
- Per-plugin health and version surfaced.
- `app.log` carries no domain event mirror.
- Audit log covers every `12` §10 category.

**Evidence:** SDK gap report; containment tests; metric agreement test.

## M14 — Production Ready (Phase 20)

- Every ratified budget met, or the miss documented and accepted.
- Keyboard-only operation verified for primary workflows.
- Glossary reconciled with implementation vocabulary.
- `uv pip install` then run on a machine with no Node and no network.
- No outbound request on any page load.
- Docker image runs non-root with one volume.
- Interop matrix executed against DCMTK, dcm4che and Orthanc; results published, failures
  triaged.
- Every `02-alt` §26 acceptance item demonstrated; `00` §11 satisfied per feature.
- Known limitations documented plainly.

**Evidence:** interop results; acceptance matrix; clean-machine install run.

---

# 4. Milestone dependencies

```
M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8 → M9 ─┬→ M10 ─┐
                                             │        ├→ M12 → M13 → M14
                                             └→ M11 ──┘
```

M10 and M11 are concurrent — the plan's main parallelism opportunity (`03-dependency-graph.md`
§4.1).

---

# 5. Milestone discipline

Three rules, each addressing a specific way milestone tracking normally fails:

1. **A milestone is binary.** "M8 at 90%" is not a state. Either traffic is observable
   against real pynetdicom or it is not.
2. **Evidence is an artifact, not an assertion.** Each criterion above names a test, a
   published output, or a demonstrable run. "Verified manually" does not satisfy a
   criterion — ADR-0022 §5 exists because unverified promises in this system are
   indistinguishable from working code until someone needs the evidence.
3. **A missed criterion is reported, not carried.** If M9's kill-test does not pass, M9 is
   not reached and Phase 12 does not start. Carrying a failed durability criterion forward
   means discovering it when a user loses a capture.

---

# 6. References

`02-phase-plan.md` · `01-work-breakdown-structure.md` · `07-definition-of-done.md` ·
`00` §11 · `02-alt` §26 · ADR-0014 · ADR-0022.
