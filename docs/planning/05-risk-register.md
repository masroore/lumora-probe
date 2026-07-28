# 05 — Risk Register

> **Project:** Lumora Probe
>
> **Document:** Risk Register
>
> **Status:** Planning Baseline
>
> **Audience:** Engineering, Architects, Product, QA

---

# 1. Purpose

Risks that could change the plan, with mitigations that are scheduled work rather than
intentions. Every mitigation names a task from `01-work-breakdown-structure.md` or is
recorded as an accepted exposure.

## 1.1 Rating

**Likelihood** and **Impact** are Low / Medium / High. **Severity** is their product,
banded: Critical (High×High), High, Medium, Low.

Risks are ordered by severity, not by phase.

---

# 2. Critical risks

## R-01 — pynetdicom cannot support inline relay as designed

**Likelihood** Medium · **Impact** High · **Severity** Critical · **Phase** 10

ADR-0003's inline proxy is the entire observation model, and pynetdicom has no
library-supported proxy mode. We need to accept an association, open a second one
upstream, mirror negotiation, and relay DIMSE messages byte-faithfully in both directions.
Nothing in the library is designed for that.

If it proves impractical, the product's primary deployment topology is gone.

**Mitigation.** T-03-03-01 resolves the threading and event-hook questions in Phase 03,
seven phases before relay is built. T-10-02-04's service-agnostic passthrough means an
unrecognized or unsupported case degrades to recording rather than failing. Permissive
standalone mode (T-10-02-03) still delivers observation without an upstream, so a partial
outcome remains a useful product.

**Residual.** If relay is impossible, ADR-0003 needs reopening and the endpoint-only model
becomes primary. Detected in Phase 03, not Phase 10 — that is the point of the spike
placement.

## R-02 — Evidence integrity is compromised by an inference or client-write path

**Likelihood** Low · **Impact** High · **Severity** Critical · **Phases** 07, 14

The product's value proposition is that a `.lpcap` handed to a vendor is trustworthy. Two
paths threaten it: a browser posting events into the stream (ADR-0016), and a rule engine
writing guesses next to socket reads (ADR-0018).

If either leaks, the artifact stops being evidence and the product's reason to exist is
gone. This is a reputational one-way door — a single shipped capture containing a
fabricated event undermines every capture.

**Mitigation.** `origin` mandatory on every envelope with absence as a validation error
(T-07-01-06), so a `jq` consumer cannot miss the distinction. Client events confined to a
dedicated endpoint, Viewer category, rate-limited (T-08-04-01). Findings written to
`analysis/` with a test asserting absence from `events.jsonl` (T-14-03-03).
Client-asserted events excluded from all inference (T-14-03-08).

**Residual.** A local process can still poison the timeline within the Viewer category.
Accepted and disclosed: bounded, marked in every envelope, counted in the manifest,
excluded from inference.

---

# 3. High risks

## R-03 — Protocol replay damages a production PACS

**Likelihood** Low · **Impact** High · **Severity** High · **Phase** 12

Protocol replay writes real C-STOREs. A misdirected 900-instance replay creates 900
duplicate objects in a live archive, and an auto-resumed replay after a crash duplicates
an unknown number because we cannot know which in-flight sends the peer committed.

**Mitigation.** Dry-run default (T-12-03-01); target never inherited from the capture
(T-12-03-02); allowlist enforced (T-12-03-03); every run audit-logged (T-12-03-04);
exclusivity refused-not-queued (T-12-03-05); no auto-resume, ever (T-12-04-03);
cancellation reports confirmed sends (T-12-04-05).

**Residual.** A user with a correctly configured allowlist can still replay into
production deliberately. That is the feature; the guardrails ensure it cannot happen
accidentally.

## R-04 — PHI leaves a hospital in a handover package

**Likelihood** Medium · **Impact** High · **Severity** High · **Phase** 15

The flagship workflow ships evidence from a customer site to a vendor, and every
architectural decision makes that artifact complete — full pixel data, full metadata. Real
de-identification is not achievable by metadata processing: burned-in annotation cannot be
removed by tag filtering at all.

**Mitigation.** Object-dropping export is the **default** (T-15-03-01); pixel-bearing
export is a deliberate opt-in (T-15-03-02). Warnings for `BurnedInAnnotation`, Secondary
Capture / US / screenshot SOP classes, unrecognized private tags and free-text
(T-15-02-04). Terminology audit forbidding "anonymize" and "de-identified" anywhere in the
product (T-15-02-05).

**Residual.** Accepted and disclosed: redaction is partial and claims no PS3.15
conformance. Naming discipline is the control, which is why the audit is a P0 task rather
than a documentation note.

## R-05 — No authentication, and the loopback assumption is wrong

**Likelihood** Medium · **Impact** High · **Severity** High · **Phases** 04, 08, 09

ADR-0009 ships no authentication. The entire perimeter is: loopback default, exposure
acknowledgment, Host allowlist, origin checks, no CORS. Any local process can read every
capture. Any web page the user visits can issue requests to `localhost:8000`, and DNS
rebinding defeats same-origin policy.

**Mitigation.** Startup refuses non-loopback bind without `--trust-network` and explains
why (T-04-04-02). Host allowlist (T-08-03-02), origin/`Sec-Fetch-Site` checks
(T-08-03-03), empty trusted-proxy list by default (T-08-03-04), WebSocket handshake origin
check (T-09-01-06). Read-only mode at a single seam (T-08-03-01) so a later auth ADR need
not move it.

**Residual.** Accepted for v1 and documented. Multi-user auth and RBAC are deferred to
their own ADR. The single-seam design is what makes that ADR cheap.

## R-06 — Phases 05–07 produce nothing visible and get compressed

**Likelihood** Medium · **Impact** High · **Severity** High · **Phases** 05–07

The four Severe cross-cutting artifacts — `Clock`/`IdGenerator`, the event envelope, the
sequencer, the error model — all land in Phases 04–07, which deliver no user-visible
capability. There is real pressure to rush toward M8.

Retrofitting any of them is a whole-codebase sweep. ADR-0022 exists specifically because
injected clock and ID cannot be added later without touching every test.

**Mitigation.** import-linter ban on `time.`/`uuid.` outside `core/` (T-05-02-04) makes
the injection non-optional from Phase 05 onward. M4, M5 and M6 are separate milestones
with binary criteria, so compression is visible rather than silent.

**Residual.** Schedule pressure is a management risk, not a technical one. The mitigation
is that the gate is mechanical.

## R-07 — Coalescing cannot hold the 100 ms budget

**Likelihood** Medium · **Impact** Medium–High · **Severity** High · **Phase** 09

The 100 ms UI budget is the only hard performance number in the PRD. Events arrive in
bursts, and HTML fan-out costs server CPU per client. If the governor cannot hold it, the
ADR-0019 architecture — server-rendered fragments — comes into question, and the fallback
is a client-side rendering layer that ADR-0019 exists to avoid.

**Mitigation.** Governor is P0 and not optional (T-09-02-01). Per-target policies
(T-09-02-02). Render-once-per-flush sharing across clients (T-09-02-04). A 5,000-event
burst test **in Phase 09** (T-09-02-05), not deferred to hardening.

**Residual.** If the budget cannot be met, the flush interval is configurable and the
honest response is to widen it and say so, rather than adopt client-side rendering.

---

# 4. Medium risks

## R-08 — Index rebuild proves lossy

**Likelihood** Low · **Impact** High · **Severity** Medium · **Phase** 06

Rebuildability underpins ADR-0004, 0011, 0013, 0020 and 0023. If anything not derivable
from captures creeps into `index.db`, "blow away the index" stops being a recovery step and
becomes data loss.

**Mitigation.** T-06-03-03 byte-compares a rebuilt projection. The two known
non-derivables are already routed elsewhere: runtime settings to `settings.toml`
(ADR-0020), job history and bookmarks to `app.db` (ADR-0023).

**Watch.** Every future table added to `index.db` must answer "is this re-derivable?".

## R-09 — Cornerstone3D bundle unusable without its DICOM parser

**Likelihood** Medium · **Impact** Medium · **Severity** Medium · **Phase** 04

ADR-0015 uses Cornerstone as a renderer only, fed by a custom image loader. If the render
path cannot be bundled independently of the parser and WASM codecs, ADR-0015 and ADR-0025
both need revisiting.

**Mitigation.** T-04-05-01 is a Phase 04 spike, scheduled before the viewer depends on it.

**Residual.** Fallback is a larger vendored artifact — cost, not blocker.

## R-10 — Codec coverage gaps in the exact cases the product exists for

**Likelihood** Medium · **Impact** Medium · **Severity** Medium · **Phase** 13

Exotic and proprietary transfer syntaxes are the bug being diagnosed, not the happy path.
pylibjpeg plus optional GDCM will not cover everything.

**Mitigation.** T-13-01-06 makes decode failure explain itself, so "we cannot decode this"
is distinguishable from "the pixel data is broken". Server-side decode (T-13-01-01) means
the answer is a property of the tool, not the user's browser.

**Residual.** Accepted: some syntaxes will not decode. Reporting that honestly is the
deliverable.

## R-11 — A plugin degrades or stalls the application

**Likelihood** Medium · **Impact** Medium · **Severity** Medium · **Phase** 16

Plugins are in-process trusted code. We can measure and disable; we cannot interrupt. An
infinite loop in a plugin stalls the event loop and no in-process design fixes it.

**Mitigation.** Exception containment per hook (T-16-02-04), time budget with auto-disable
(T-16-02-05), per-plugin health and version surfaced (T-17-02-02), SDK compatibility gate
(T-16-02-03), no installation over the API (T-16-02-07), explicit trust disclosure
(T-16-02-09).

**Residual.** Accepted and documented honestly. A UI implying capability enforcement would
be worse than saying nothing.

## R-12 — Ring buffer writes PHI to disk at a site that did not expect it

**Likelihood** Medium · **Impact** Medium · **Severity** Medium · **Phase** 11

ADR-0008 ships the buffer **enabled**, a considered deviation from `12` §15. That means
pixel data lands on disk without an explicit user action.

**Mitigation.** Documented events-only switch (T-11-01-02) for sites that cannot have PHI
on disk unprompted. Bounded by default (30 min / 2 GB). Retention state visible
(T-11-01-03). Path containment and network-FS refusal already enforced (T-04-02-04,
T-04-02-05).

**Residual.** Accepted: a disabled-by-default buffer is a feature nobody discovers until
after they needed it, which is the failure ADR-0008 optimises against.

## R-13 — Two stores drift apart

**Likelihood** Low · **Impact** Medium · **Severity** Medium · **Phase** 06

ADR-0004 keeps capture directories and SQLite coherent by convention; JSONL has no
referential integrity.

**Mitigation.** Directory is the source of truth; rebuild is the reconciliation
(T-06-03-03). Digest verification (T-06-02-07). Gap-free sequence makes loss provable
(T-07-02-04).

## R-14 — Scope creep toward a PACS archive

**Likelihood** Medium · **Impact** Medium · **Severity** Medium · ongoing

Charter §6 and `04` §6 forbid it, yet `07` §4 modelled Study as a durable aggregate and
`08` §6 exposes study resources. The pull is structural, not hypothetical.

**Mitigation.** ADR-0013 makes studies a projection; T-13-03-01 keeps rows derived. A
pinnable permanent library was explicitly rejected as the same thing in disguise.

**Watch.** Any request for durable study retention reopens ADR-0013 rather than being
implemented.

---

# 5. Low risks

| ID | Risk | Phase | Mitigation |
|----|------|-------|------------|
| R-15 | Committed build artifacts go stale | 04 | CI rebuild-and-compare (T-04-05-04) |
| R-16 | SQLite concurrency under load | 06 | Spike (T-06-01-05); WAL, single writer, network-FS refusal |
| R-17 | Clock semantics differ across macOS/Linux on suspend | 07 | `ClockAnomalyDetected` surfaces it rather than smoothing (T-07-02-07) |
| R-18 | Interop suite never runs because it is not gating | 20 | Scheduled job, not just marked (T-03-02-03); results published (T-20-01-05) |
| R-19 | Glossary drifts from implementation vocabulary | 18 | Reconciliation is a P0 task (T-18-03-01) |
| R-20 | Accessibility deferred to the end and then dropped | 18 | Keyboard-only is P0 (T-18-02-05); command palette built in Phase 13 |
| R-21 | Report PDF requires an unwanted dependency | 15 | T-15-01-02 decides explicitly; print-to-PDF is an acceptable answer |
| R-22 | Data directory from a newer version corrupted | 04 | Version marker with refusal (T-04-02-06, T-19-01-07) |

---

# 6. Accepted exposures

Deliberate, documented, and not to be re-litigated during implementation. Each is an ADR
consequence, listed here so nobody "fixes" one mid-phase.

| Exposure | Source | Why accepted |
|----------|--------|--------------|
| No authentication in v1 | ADR-0009 | Loopback-first tool; a credential prompt on `localhost` trains users to bypass it |
| Plugins have full process trust | ADR-0021 | CPython offers no in-process restriction; a permissions UI would imply enforcement that does not exist |
| Redaction is partial, no PS3.15 claim | ADR-0026 | Burned-in annotation is unremovable by metadata processing |
| Ring buffer on by default | ADR-0008 | An off-by-default buffer is discovered only after it was needed |
| C-MOVE sub-operations invisible | ADR-0024 | Not on our path; reported as a finding with remediation |
| No cross-collector total order | ADR-0017 | Correct for a non-distributed system; `06` §9 already disclaims it |
| Probe is a live-path failure point | ADR-0003 | Inherent to inline observation; byte-faithful relay is the mitigation |
| Component-weighted, not unit-heavy | ADR-0022 | Deliberate `13` §4 deviation; the bugs are in integration, not value objects |

---

# 7. Risk-to-phase map

| Phase | Risks live |
|-------|-----------|
| 04 | R-05, R-09, R-15, R-22 |
| 05–07 | R-02, R-06, R-08, R-13, R-16, R-17 |
| 08–09 | R-05, R-07 |
| 10 | **R-01** |
| 11 | R-12 |
| 12 | R-03 |
| 13 | R-10 |
| 14 | R-02 |
| 15 | R-04, R-21 |
| 16 | R-11 |
| 18 | R-19, R-20 |
| 20 | R-18 |
| ongoing | R-14 |

Phase 10 carries the single Critical technical risk, and it is mitigated four phases
earlier by the Phase 03 spike. That placement is the plan's main risk-management decision.

---

# 8. References

`01-work-breakdown-structure.md` · `02-phase-plan.md` · `03-dependency-graph.md` ·
`00-architecture-review-findings.md` §5 · ADR-0003 · ADR-0008 · ADR-0009 · ADR-0016 ·
ADR-0018 · ADR-0019 · ADR-0021 · ADR-0022 · ADR-0024 · ADR-0026.
