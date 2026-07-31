# Cross-Product Sharing Audit and Refactoring Plan

**Date:** July 31, 2026  
**Status:** Planning only — **do not implement from this document without the ADR gate**  
**Audience:** Handover implementer  
**Scope audited:** `src/probe_lite/`, `src/sender_lite/`, `src/lumora_lite_common/`, and `src/lumora_probe/`

---

## 1. Executive decision record

This audit was conducted after an explicit design review. The approved direction is:

1. Create a **new neutral top-level package**, `src/lumora_dicom_common/`.
2. Ship it in the **existing `lumora-probe` wheel** initially; do not create a separate distribution now.
3. Use a **staged extraction**:
   - Stage 1: framework-free DICOM identity/normalization primitives.
   - Stage 2: only after a proof step, a narrow `pynetdicom` compatibility adapter.
   - Never move product workflows into the neutral package.
4. Preserve each product’s current observable behavior. The neutral package supplies low-level results; each product retains its own policy wrapper and exception/result types.
5. An accepted ADR is a hard prerequisite. Existing ADR-0028 and the Lite PRD currently forbid Lite ↔ Lumora Probe source sharing.

This is **not** approval to import `lumora_lite_common` from `lumora_probe`, to import `lumora_probe` from either Lite package, or to turn the neutral package into a second application layer.

---

## 2. Why an ADR is mandatory

The repository has an explicit, accepted isolation decision:

- `docs/lumora-probe-lite-prd.md` §1.2 and TC-01 describe the Lite tools as independent from `src/lumora_probe/`.
- ADR-0028 limits `lumora_lite_common` to Probe Lite and Sender Lite. Its scope explicitly excludes the parent application.
- `CLAUDE.md` and `AGENTS.md` require a new ADR before changing an accepted architecture decision.

The new ADR must supersede **only the cross-product prohibition needed for narrowly defined DICOM infrastructure**. It must retain all existing Lumora Probe slice rules and preserve `lumora_lite_common` as Lite-only.

### Required ADR decision

Create the next available ADR (currently expected to be ADR-0034) before code changes. It must state:

| Topic | Required decision |
|---|---|
| New package | `lumora_dicom_common`, top-level under `src/`, included in the existing wheel |
| Dependency direction | `lumora_dicom_common` imports no `lumora_probe`, `probe_lite`, `sender_lite`, web framework, database, event-bus, clock, or ID code |
| Stage 1 contents | UID/AE low-level parsing and normalization only; stable constants only where their semantics are genuinely universal |
| Stage 2 contents | Optional and separately approved `pynetdicom` compatibility/factory helpers; no listener/SCU lifecycle |
| Compatibility | Existing product validation policy, public names, exception types, logging, exit codes, and defaults stay unchanged |
| Prohibited contents | Capture format, filesystem persistence, catalog/batching, DICOM listener lifecycle, sender/replay workflow, CLI config parsing, logging, signals, event bus, metrics, audit, or web code |
| Packaging | Existing single wheel first; a separate distribution is a future option, not present work |
| Test policy | Component-focused tests; no sleeping in Lumora Probe tests; Lite behavior remains byte-for-byte/contract compatible where existing tests assert it |

Do **not** amend ADR-0028 in place. Link the new ADR to ADR-0028 and the Lite PRD, explain the narrow exception, and update `docs/adr/README.md`.

---

## 3. Audit method and source evidence

### 3.1 Review method

- Enumerated the public functions/classes across all four source roots.
- Checked import relationships: Lite packages import `lumora_lite_common`; `lumora_probe` currently imports neither Lite package nor the Lite common package.
- Compared DICOM identity, `pynetdicom`, listener, sender, storage, config, lifecycle, and logging seams.
- Checked current import-linter contracts, wheel package list, and relevant tests.

### 3.2 Key code locations

| Concern | Existing locations | Finding |
|---|---|---|
| Lite shared helpers | `lumora_lite_common/{logging,signals,config_validators,uids}.py` | Correct existing Lite-only extraction from ADR-0028 |
| Application DICOM value objects | `lumora_probe/shared/value_objects.py` | Independent `AETitle` and `DICOMUID` implementations overlap in low-level validation only |
| Lite UID use | `lumora_lite_common/uids.py`, `probe_lite/storage.py`, `sender_lite/catalog.py` | Already shared within Lite; candidate source for neutral low-level primitive |
| Lite SCP | `probe_lite/receiver.py` | `pynetdicom` SCP setup plus Lite storage/logging/lifecycle behavior |
| Lite SCU | `sender_lite/sender.py` | C-ECHO/C-STORE association operations plus study batching/result accounting |
| Application DICOM plane | `lumora_probe/associations/network.py` | Listener, SCU, protocol tracing, event ingress, audit, lifecycle, and replay-facing send capability |
| Application persistence | `lumora_probe/captures/{format,service,repository}.py`, `core/paths.py` | Capture-specific format and content-addressed storage; not comparable to Lite filesystem receipt |
| Application config/logging | `lumora_probe/core/{config,logging}.py`, `lumora_probe/cli.py` | Different product-level contracts; no extraction target |
| Wheel build | `pyproject.toml` `[tool.hatch.build.targets.wheel]` | Explicit package list must include the new neutral package |

---

## 4. Findings: all duplicated, shareable, and deliberately separate subsystems

### 4.1 Already shared correctly — retain unchanged

| Subsystem | Current implementation | Disposition |
|---|---|---|
| Text/JSON event logger engine | `lumora_lite_common.logging.EventLogger`; product-specific `ProbeLogger` / `SenderLogger` label maps | **Keep Lite-only.** Lumora Probe uses structured `structlog`, correlation and redaction conventions rather than stdout text/JSONL. |
| Portable signal install/restore | `lumora_lite_common.signals` | **Keep Lite-only.** The callback mechanics are common; application lifecycle is asynchronous service orchestration, not a CLI signal callback. |
| CLI leaf validators | `lumora_lite_common.config_validators` | **Keep Lite-only.** Port/PDU policy differs materially in the application. |
| Lite UID handling | `lumora_lite_common.uids` | **Keep for compatibility, but adapt it to neutral Stage 1 primitives.** Preserve its public functions and reason codes. |

No new shared package should replace `lumora_lite_common` wholesale. It has an intentionally Lite-specific public API and behavior.

### 4.2 New Stage 1 candidates — extract after ADR approval

| ID | Subsystem | Duplicate/overlap evidence | Target in `lumora_dicom_common` | Product adapters that must remain | Priority |
|---|---|---|---|---|---|
| S1-01 | DICOM UID lexical parsing | `lumora_lite_common.uids.validate_uid()` and `lumora_probe.shared.value_objects.DICOMUID` each check dotted-decimal UID form and 64-character limit | A pure lexical parser/normalizer returning a value or structured reason; no product exception class | Lite keeps `validate_uid`, `is_valid_uid`, `safe_uid`, its missing/multivalue behavior and reasons. Lumora Probe keeps `DICOMUID` and `domain_invariant` errors. | High |
| S1-02 | AE-title low-level ASCII/length inspection | `validate_ae_title()` and `AETitle.__post_init__()` each enforce 1–16 ASCII bytes | Pure result-producing inspection/normalization; it must not decide product policy on whitespace/control characters | Lite validator retains current permissive behavior. Lumora Probe `AETitle` retains printable/non-whitespace policy and its domain errors. | High |
| S1-03 | Universal DICOM transport constants | Default DICOM port `11112`, default PDU `16382`, and success code `0x0000` occur in the DICOM endpoints | Constants only, with names that do not imply a universal security/config policy | Each product keeps its own listener port range, max-PDU range, and configuration defaults/wrappers. Do not extract range validators. | Low |
| S1-04 | DIMSE response status extraction | `sender_lite.sender._read_status()` and `lumora_probe.associations.network._status_code()` both turn response status into an integer | A deliberately defensive status reader with an explicit invalid/missing result | Sender still maps status to success/warning/failure and exit code. Application still creates `DICOMEchoResult`/`DICOMStoreResult` and emits events. | Medium |

#### Stage 1 API constraints

The implementer must not make a neutral value object that becomes the application’s domain model. Use plain immutable result records or pure functions. The package must not import `pydicom`; its input API should accept strings/scalars. Product adapters may unwrap `pydicom` values before calling it.

The neutral package must not make these behavior changes:

- Reject a Lite AE title merely because it is whitespace/control ASCII.
- Change Lumora Probe’s `DomainInvariantError` type or message family.
- Remove Lite `REASON_MISSING`, `REASON_MULTI_VALUED`, or `REASON_INVALID` behavior.
- Merge port/PDU validators. Current policies differ intentionally:
  - Lite generic port: `1..65535`; Lite max PDU: `1..16777215`.
  - Lumora Probe listener: non-privileged `1024..65535`; listener max PDU: `4096..131072`.

### 4.3 Conditional Stage 2 candidates — proof first, then decide

| ID | Subsystem | Existing overlap | What may be shared | Explicit non-goal | Priority |
|---|---|---|---|---|---|
| S2-01 | Lazy `pynetdicom` import compatibility | Probe Lite uses a public/private `ALL_TRANSFER_SYNTAXES` fallback; Lumora Probe and Sender Lite each perform local imports and dependency failure handling | A tiny dependency-loading facade that exposes tested third-party symbols and produces consistent dependency-unavailable details | It must not import product config, log, events, storage, or lifecycle code. | Medium |
| S2-02 | Receive-runtime third-party flags | Probe Lite and Lumora Probe both set `LOG_HANDLER_LEVEL`, `UNRESTRICTED_STORAGE_SERVICE`, and `STORE_RECV_CHUNKED_DATASET` | An idempotent function that applies only these `pynetdicom` runtime settings | Do not hide or own global configuration policy. Caller must invoke it explicitly before AE creation. | Medium |
| S2-03 | Storage/verification presentation-context wiring | Both SCP implementations add storage contexts using all transfer syntaxes and support C-ECHO | A parameterized context-adder using caller-supplied context families; app can additionally request Query/Retrieve contexts | Do not make one generic `build_listener()` or choose the application’s vs Lite’s supported-context profile. | Medium |
| S2-04 | Minimal SCU AE configuration | Sender Lite C-ECHO/C-STORE and application SCU both construct `pynetdicom.AE`, set identities/timeouts, associate, and inspect status | Only a narrow, synchronous construction helper if Stage 2 proof shows it removes real duplication without obscuring tests | Do not move `Sender.send_study`, `DICOMSCUClient`, replay integration, async conversion, result records, cancellation, or retry semantics. | Low / high risk |

#### Stage 2 proof gate

Before moving production imports, build a **test-only spike or focused unit/component test set** that verifies the proposed helper against the exact installed `pynetdicom` version and both product use cases.

Proceed only if all conditions hold:

1. The helper has no product-package imports.
2. Probe Lite still supports its fallback import behavior and unrestricted storage operation.
3. Lumora Probe still adds Query/Retrieve contexts and PDU trace handlers where required.
4. Sender Lite keeps one association per Study Batch (ADR-0027).
5. Application calls remain off the asyncio loop where they are today.
6. Existing receiver, sender transport, application network, and replay protocol tests stay unchanged or require only import redirection.

If the proof needs a callback, protocol, product event, clock, ID generator, storage abstraction, or lifecycle object, **stop**. Keep that code product-owned.

### 4.4 Similar but not shared — deliberately retain product ownership

| Subsystem | Why it looks similar | Why it must not be extracted |
|---|---|---|
| SCP listener lifecycle | Probe Lite `ProbeReceiver` and application `DICOMListener` both start a threaded server and handle C-ECHO/C-STORE | Application owns audit records, bus ingress, PDU traces, health, drain/flush phases, IDs, clocks, and capture sinks. Lite owns stdout logging and a blocking shutdown event. |
| SCU association lifecycle | Sender Lite and application `DICOMSCUClient` both associate and send/echo | Sender Lite has exact Study Batch association boundaries, cancellation, presentation-context negotiation reporting, status classification, and exit-code contract. Application has async façade, replay ownership, event/audit integration. |
| C-STORE handler | Both receiver stacks handle C-STORE | Lite persists a local file or raw fallback; application derives observation/capture events and uses injected sinks. Different correctness and failure semantics. |
| DICOM filesystem storage | Probe Lite writes UID-path files; application has capture package/content-addressed object storage | Different data model, atomicity/integrity rules, file layout, security containment, and retention behavior. |
| DICOM file metadata extraction | Sender Lite catalog reads Part 10 files; application reads datasets for capture/study/report flows | Catalog’s duplicate detection, deterministic grouping, and rejection reasons are a Lite workflow. Application uses projections and capture ownership. |
| Config source/precedence engines | Both use argparse and dataclass-style resolved config | Probe Lite is CLI > environment > defaults; Sender Lite is CLI > TOML > defaults; Lumora Probe has immutable startup/runtime setting tiers, provenance, and security gates. |
| Logging | Every product logs transport outcomes | Lite uses stdout text/JSONL with label maps; application uses structured logging with correlation/redaction. Shared log engine would weaken contracts. |
| Signal/process shutdown | Lite CLIs react directly to OS signals | Lumora Probe lifecycle owns async services and graceful drain; no safe generic adapter provides meaningful reuse. |
| Time/duration handling | All transport code records durations | Lumora Probe must use injected `Clock`/`IdGenerator` outside `core` under ADR-0022; Lite uses direct `time`. A cross-product timing helper would violate or dilute this boundary. |
| Error/result types | All products report failure states | Public result records encode product-specific CLI/event semantics. Do not replace them with a universal result hierarchy. |
| CLI entry shims | Both Lite `__main__.py` files are nearly identical | Seven-line package-specific shims are not a worthwhile abstraction. |

### 4.5 Explicitly excluded subsystems

The following have no valid cross-product shared-library destination in this plan:

- Lumora Probe event envelope, event bus, event ordering, PDU trace, event catalog.
- `.lpcap` format, capture manifests, capture handover/redaction, SQLite/storage layout.
- Lumora Probe web/API, plugins, reports, studies projections, settings, operations, metrics, audit.
- Sender Lite catalog model, Study Batch grouping, association-per-Study rule, CLI exit codes.
- Probe Lite raw/parsed storage paths, output directory semantics, CLI process behavior.
- All network exposure/security settings and gates.

---

## 5. Required target architecture

```text
src/
├── lumora_dicom_common/                 # New, neutral, no product imports
│   ├── __init__.py
│   ├── identifiers.py                   # Stage 1: lexical UID/AE primitives
│   ├── status.py                        # Stage 1: defensive DIMSE status read, if justified
│   ├── constants.py                     # Stage 1: truly universal constants only, if justified
│   └── pynetdicom_runtime.py            # Stage 2 only; do not create before proof passes
├── lumora_lite_common/                  # Remains Lite-only compatibility facade
├── probe_lite/                          # Product adapters/workflows
├── sender_lite/                         # Product adapters/workflows
└── lumora_probe/                        # Application domain/adapters/workflows
```

### Dependency rules

Allowed:

```text
probe_lite       ─┐
sender_lite      ─┼──> lumora_dicom_common
lumora_probe     ─┘

probe_lite       ─┐
sender_lite      ─┴──> lumora_lite_common
```

Forbidden:

```text
lumora_dicom_common -> lumora_probe | probe_lite | sender_lite | lumora_lite_common
lumora_probe       -> lumora_lite_common
probe_lite          -> lumora_probe
sender_lite         -> lumora_probe
```

`lumora_dicom_common` must use only the standard library in Stage 1. Stage 2 may have local/lazy `pynetdicom` access only if the ADR and proof gate approve it.

---

## 6. Implementation plan — execute in order

### Phase 0 — decision and safety baseline

**Do not write production code before this phase completes.**

1. Add new ADR described in §2.
2. Update `docs/adr/README.md` index and the Lite PRD/README wording that says no source is shared with the parent application. New wording must explain the narrow neutral infrastructure exception without implying product coupling.
3. Add an import architecture assertion. Preferred approach: extend `.importlinter` with a contract that prevents `lumora_dicom_common` from importing any product package. If import-linter cannot express this cleanly, add a focused AST import test as a fallback; do not omit the guard.
4. Capture behavior baselines before refactoring:
   - Lite UID reason-code cases.
   - Lite AE-title cases, including existing permissive whitespace/control ASCII behavior.
   - Lumora Probe `AETitle` and `DICOMUID` valid/invalid cases and exception family.
   - Sender and application DIMSE status extraction cases: `None`, no `Status`, numeric status, malformed status.
5. Run the focused baseline suite and record that it passes before changing imports.

**Exit condition:** ADR accepted, architecture guard exists, baseline tests pass. Otherwise stop.

### Phase 1 — neutral Stage 1 primitives

**Files to add:**

- `src/lumora_dicom_common/__init__.py`
- `src/lumora_dicom_common/identifiers.py`
- Optionally `src/lumora_dicom_common/status.py`
- Optionally `src/lumora_dicom_common/constants.py`
- `tests/test_dicom_common_identifiers.py`
- `tests/test_dicom_common_status.py` if status extraction moves

**Files likely to modify:**

- `pyproject.toml` — add `src/lumora_dicom_common` to Hatch wheel packages.
- `.importlinter` or dedicated import-boundary test.
- `src/lumora_lite_common/uids.py` — adapt internally while preserving its public API/reasons.
- `src/lumora_lite_common/config_validators.py` — adapt only if it can preserve all current Lite behavior exactly.
- `src/lumora_probe/shared/value_objects.py` — call neutral lexical helpers inside existing `AETitle`/`DICOMUID`; keep application policy and domain errors local.
- `src/sender_lite/sender.py` and `src/lumora_probe/associations/network.py` — only if status helper is proven behavior-equivalent.
- Existing tests listed in §7.

**Rules:**

- Write neutral tests first for lexical behavior. Do not import product error types into these tests.
- Migrate one product adapter at a time.
- Run the adapter’s current tests immediately after each migration.
- Preserve all public imports from `lumora_lite_common` and `lumora_probe.shared.value_objects`.
- Do not move `AETitle` or `DICOMUID` classes. They remain application value objects.
- Do not use `pydicom` in neutral identifier code. MultiValue/DataElement unwrapping stays in Lite/application adapters.

**Exit condition:** neutral tests, all Lite common tests, application domain tests, sender transport tests, receiver tests, and import-linter all pass with no behavior change.

### Phase 2 — `pynetdicom` extraction proof

**This is a decision gate, not an automatic implementation phase.**

1. Map the exact third-party calls in:
   - `probe_lite/receiver.py::_build_ae`
   - `sender_lite/sender.py::{echo,send_study}`
   - `lumora_probe/associations/network.py::{DICOMListener._build_ae,DICOMSCUClient.*}`
2. Propose the smallest helper surface. Start with only dependency loading and receive-runtime flag application.
3. Write tests that use fakes/monkeypatching to prove:
   - fallback import behavior is preserved;
   - each caller receives the symbols/context families it needs;
   - no product callback or state appears in the neutral API;
   - the global flags are applied predictably and explicitly.
4. Compare the proposed helper to the existing three sites. If it does not remove enough duplication to justify a new dependency boundary, reject the extraction and record the reason in the ADR follow-up or implementation notes.

**Exit condition:** explicit go/no-go recorded. No silent scope expansion.

### Phase 3 — optional narrow `pynetdicom` adapter

Proceed only after Phase 2 is a documented **go**.

**Possible files:**

- `src/lumora_dicom_common/pynetdicom_runtime.py`
- `tests/test_dicom_common_pynetdicom_runtime.py`
- Minimal import/call-site edits in `probe_lite/receiver.py` and `lumora_probe/associations/network.py`

**Non-negotiable exclusions:**

- No `DICOMListener`, `ProbeReceiver`, `DICOMSCUClient`, or `Sender` moves.
- No listener/server start/stop helper.
- No async wrapper.
- No event/audit/logging/capture/study/cancel callback.
- No global singleton that owns AE instances.

**Exit condition:** all current component/transport tests pass; code review confirms the helper is mechanical rather than a product workflow abstraction.

### Phase 4 — documentation, package verification, and cleanup

1. Update package tree/readme documentation to show `lumora_dicom_common` as neutral infrastructure and `lumora_lite_common` as Lite-only.
2. Ensure API docs identify public vs internal helper functions.
3. Build the wheel and verify all five packages are present:
   - `lumora_probe`
   - `probe_lite`
   - `sender_lite`
   - `lumora_lite_common`
   - `lumora_dicom_common`
4. Re-run all quality gates in §7.
5. Keep the diff narrow. Do not opportunistically reformat/rename unrelated DICOM code.

---

## 7. Verification matrix

### Focused tests during the work

| Change | Tests to run immediately |
|---|---|
| Neutral UID/AE primitives | New neutral tests; `tests/test_common_uids.py`; `tests/test_common_config_validators.py`; `tests/test_phase05_domain.py`; `tests/test_phase05_primitives.py` |
| Lite storage/catalog adapter | `tests/test_storage.py`; `tests/test_sender_catalog.py`; `tests/test_receiver.py` |
| Status helper | `tests/test_sender_transport.py`; `tests/test_phase10_network.py`; `tests/test_phase12_replay.py`; `tests/test_phase12_replay_protocol.py` |
| `pynetdicom` runtime helper | `tests/test_receiver.py`; `tests/test_sender_transport.py`; `tests/test_phase10_network.py`, plus newly added helper tests |
| Packaging/docs | Build the wheel; installed entry-point/module smoke tests if the repository’s existing packaging tests cover them |

### Required final commands

```console
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run lint-imports --no-cache
uv run basedpyright src/lumora_probe/core src/lumora_probe/shared
npm run check:assets
```

Run `uv sync --locked` first when the environment is not already synced. Do not run interop by default. If a Stage 2 `pynetdicom` change warrants it, schedule it using the repository’s opt-in interop procedure rather than adding it to the default gate.

### Additional acceptance checks

- `probe-lite --help`, `sender-lite --help`, and application import/startup smoke paths keep their current behavior.
- Sender Lite exit codes remain `0`, `1`, `2`, `130` as currently documented.
- Probe Lite accepts the same CLI/environment input as before.
- Lumora Probe keeps loopback/network-exposure gates unchanged.
- No Lite package imports `lumora_probe`; no Lumora Probe package imports `lumora_lite_common`.
- New package does not import `time` or `uuid`; it must remain compatible with the application’s ADR-0022 boundaries.
- No new third-party dependency without a separate ADR decision.

---

## 8. Risks and stop conditions

| Risk | Why it matters | Required mitigation / stop condition |
|---|---|---|
| Architecture violation | Existing docs explicitly forbid cross-product sharing | No production change before ADR acceptance and an import-boundary guard |
| Accidental Lite behavior change | Lite AE-title policy is currently broader than application policy | Preserve product wrappers; add characterization tests before migration |
| Domain-model leakage | Moving application value objects would make neutral code application-shaped | Extract only lexical results/functions; retain `AETitle` and `DICOMUID` in `lumora_probe.shared` |
| Over-abstracted transport | A common listener/SCU hides different lifecycle/cancellation/event semantics | Stop when helper requires callbacks, events, clocks, IDs, storage, or async ownership |
| Third-party global configuration | `pynetdicom` settings are process-global | Keep runtime configuration explicit, idempotent, tested, and narrowly scoped |
| Packaging omission | Hatch has an explicit wheel package list | Add wheel-content check in the change’s verification steps |
| Test nondeterminism | Application disallows direct `time`/`uuid` outside `core` | Neutral Stage 1 has no time/ID behavior; preserve injected application collaborators |
| Scope creep after GA | Lumora Probe v0.1.0 is signed off | Treat this as a new approved maintenance milestone only after ADR/plan acceptance |

---

## 9. Handover checklist for the implementing model

Before editing source:

1. Read `AGENTS.md`, `CLAUDE.md`, ADR-0028, the new ADR, the Lite PRD, and this plan.
2. Confirm whether the ADR has been accepted. If not, write/review the ADR only; do not refactor code.
3. Confirm repository status; do not overwrite unrelated untracked work.
4. Implement Phase 0 completely before Phase 1.
5. Keep the first code change to Stage 1 only. Do not create the `pynetdicom` module merely because this plan names it.
6. Preserve public APIs and existing tests. Add characterization tests rather than changing expectations to match a new abstraction.
7. After every adapter migration, run its focused tests.
8. If a candidate needs product-level state or has fewer than two meaningfully equivalent call sites, leave it where it is and document the rejection.
9. Do not implement a generic DICOM application framework. The purpose is to remove mechanical duplication, not merge products.
10. Finish with all commands in §7 and update docs generated by any changed public contract.

---

## 10. Final recommendation

There is **real, bounded cross-product sharing opportunity**, but only at the DICOM-mechanical layer. The first valuable extraction is a neutral, standard-library-only lexical foundation for UID and AE-title handling, with product-specific wrappers preserving existing semantics. A tiny `pynetdicom` adapter may be justified later, but only after a focused proof demonstrates that it stays mechanical.

The large apparent overlaps — receiver/listener lifecycle, sender/SCU operation, storage, cataloging, config, logging, signals, and event processing — are not duplicate libraries waiting to be merged. They embody different product contracts. Refactoring them into a shared framework would violate the reason the products are separated and should be rejected.
