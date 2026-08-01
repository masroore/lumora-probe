# Production-Readiness Release-Closure Implementation Plan

**Status:** Execution-ready implementation plan; code not started  
**Prepared:** 2026-08-01  
**Baseline:** `31e7b1b` on `master`  
**Source audit:** `docs/other/lumora-probe-production-readiness-audit-and-implementation-plan.md`  
**Audience:** execution agent with limited repository context  
**Scope:** remaining release-closure work only

## 1. Purpose

This plan closes the release-readiness gaps left after the production composition remediation:

1. graceful and forced shutdown while DICOM traffic is active;
2. adversarial capture ownership, thread-ingress saturation, and shutdown tests;
3. production-scale pagination, index rebuild, and ring-buffer expiry measurement/remediation;
4. strict type checking across every `lumora_probe` application slice;
5. removal or explicit ownership of all current dependency compatibility warnings;
6. installed wheel and sdist verification on Linux, macOS, and Windows;
7. final evidence and release-document reconciliation.

This document is an execution specification. It does not authorize unrelated features or a broad
rewrite. Complete work packages in order. Make every task its own atomic commit using the commit
message shown under that task. Do not combine work packages into one commit.

## 2. Verified Starting Point

Revalidate this table before implementation. Stop and update this plan if the baseline changed in a
way that invalidates a target file or contract.

| Area | Current evidence | Remaining defect or evidence gap |
|---|---|---|
| Full suite | `540 passed, 17 skipped, 166 warnings` | Warnings are not release-clean. |
| EventBus thread ingress | `BoundedSemaphore`, pending count, completion callbacks, unit saturation test | DICOM behavior under saturation and process shutdown is not proved. |
| Capture ownership | One `threading.RLock` protects active sessions and writers | Lock protocol is undocumented; no concurrent C-STORE/stop/interrupt stress exists. |
| Process acceptance | Real HTTP/DICOM C-ECHO/C-STORE, restart, settings, SIGTERM | No sustained active traffic or forced shutdown-deadline case. |
| Capture pagination | `list_captures_page()` and persisted `object_size` exist | Sort/filter fallback and point lookup still materialize complete collections; no scale gate. |
| Projection pagination | `_SQLiteResourceStore.list_page()` applies SQL `LIMIT/OFFSET` | No repository contract, query-plan assertion, deep-page evidence, or server-side sort/filter. |
| Index rebuild | Capture rows are indexed with projection rebuild disabled, then projections rebuild once | No scale, write-amplification, failure, or process-readiness benchmark. |
| Ring expiry | A persisted `records.jsonl` is rewritten after any eviction | Rewrite cost grows with retained bytes and is unmeasured at production retention. |
| Strict typing | `core`, `shared`, `analysis`, `plugins`, and `bootstrap.py` pass independently | Current strict errors: associations 3, captures 15, studies 11, replay 11, settings 6, web 27, reports 76. |
| Compatibility | Locked pydicom 3.0.2, pynetdicom 3.0.4, FastAPI 0.141.0, Starlette 1.3.1 | 166 warnings; direct deprecated fixture calls and a Starlette TestClient transport warning. |
| OS support | Source suite runs in a 3-OS CI matrix | Wheel/sdist production smoke was only proved locally on macOS. |

Current warning inventory:

| Warning | Count | Initial owner |
|---|---:|---|
| pydicom `write_like_original` deprecation | 42 | Test fixture and sender/replay write paths |
| pydicom `Dataset.is_little_endian` deprecation | 20 | Receiver/decode/study fixtures |
| pydicom `Dataset.is_implicit_VR` deprecation | 20 | Receiver/decode/study fixtures |
| pydicom `FileDataset.is_little_endian` deprecation | 30 | Sender catalog fixtures |
| pydicom `FileDataset.is_implicit_VR` deprecation | 30 | Sender catalog fixtures |
| Unknown `MediaStorageApplicationTitle` keyword | 22 | Sender fixtures |
| Deliberately invalid IS value | 1 | Negative sender catalog test |
| Starlette TestClient using deprecated `httpx` transport | 1 | Test dependency configuration |

## 3. Non-Negotiable Constraints

1. Preserve ADR-0002: one asyncio-owned EventBus and one explicit pynetdicom thread boundary.
2. Preserve ADR-0017: only bus-assigned `sequence` orders events; no wall-clock ordering.
3. Preserve ADR-0004/0007 evidence semantics: successful C-STORE acknowledgment cannot precede
   required durable object/evidence persistence.
4. Capture/persistence paths never silently drop. UI paths may retain their documented drop-oldest
   behavior with exact counters.
5. Capture directories remain authoritative. `index.db` remains disposable. `app.db` remains
   authoritative.
6. No `time` or `uuid` imports outside `core`; tests use injected clocks/IDs except true
   process-boundary elapsed-time harnesses.
7. No cross-slice internal imports. Add the smallest `contracts.py` protocol when a boundary must
   expand.
8. No real or de-identified patient data. All DICOM data and UIDs must remain synthetic under the
   repository's test UID root.
9. Do not add auth/RBAC, pcap import, byte-exact replay, remote collectors, Prometheus exposition,
   or PS3.15 de-identification.
10. Do not weaken fsync, Host/Origin policy, startup exposure gates, or failure reporting to make a
    benchmark or test pass.
11. Do not suppress strict typing with directory-wide exclusions, blanket `Any`, blanket ignores,
    or reduced diagnostic levels.
12. Do not suppress warnings globally. A targeted warning assertion is allowed only when the
    warning is the behavior under test.

## 4. Required End State

Release closure requires all of the following:

- bounded DICOM thread submissions with documented saturation status and observable counters;
- deterministic capture writer ownership under simultaneous C-STORE, event, stop, and interrupt;
- clean process exit inside the configured grace period under ordinary active traffic;
- explicit interrupted evidence after a forced deadline, followed by successful restart recovery;
- server-side, bounded pagination for supported sort/filter combinations and direct point lookup;
- one projection rebuild per full index rebuild and no ready state over partial current-process data;
- ring persistence whose eviction write cost is bounded by segment size, not total retained bytes;
- strict BasedPyright over all `src/lumora_probe` code from one canonical command;
- zero unexpected warnings in the default suite;
- wheel and sdist installed-production smoke on all three declared OS families;
- release docs that cite CI artifacts and do not claim unproved performance or OS support.

## 5. Work Package 0 - Freeze Decisions and Baselines

### PRC-000 - Revalidate baseline and create execution ledger

**Priority:** P0  
**Files:** this plan; implementation PR description; no production source

Steps:

1. Record `git rev-parse HEAD`, `git status --short`, Python version, OS, and `uv --version`.
2. Run the mandatory gates and save summarized output in the PR:
   `uv run pytest -q`, Ruff check/format, import-linter, and current BasedPyright command.
3. Run each unchecked slice independently and update the strict-error counts in the PR. Counts are
   planning information, not acceptance targets; all must reach zero.
4. Capture warning category/count output from one unfiltered full test run.
5. Confirm the original readiness audit's unchecked provider item against
   `build_production_app()`. Required production routes must use real providers. If any route still
   uses an empty/null provider for a capability claimed by v0.1.0, stop and add a separately scoped
   finding before continuing.
6. Confirm all existing test DICOM files are generated synthetic fixtures.

Acceptance:

- baseline and differences from this document are explicit;
- worktree starts clean or unrelated changes are identified and left untouched;
- no finding is silently treated as closed because a unit test exists.

Commit: none; evidence belongs in the implementation PR.

### PRC-001 - Ratify capture ownership and saturation semantics

**Priority:** P0  
**Files:** next available ADR number; `docs/adr/README.md`

Create `ADR-0036` if that number remains available; otherwise use the next unallocated number and
update all plan references. Write and accept the ADR before changing concurrency behavior. It must
choose and specify the following design unless review identifies a concrete violation of ADR-0002:

1. `CaptureEngine` owns one re-entrant session lock. That lock serializes session lookup,
   lifecycle transition, writer append, writer manifest update, seal, and removal.
2. Lock order is ring-buffer lock, then capture-session lock, then package-writer internals. No code
   may acquire them in reverse order.
3. PDU/object fidelity remains off bus, because bus envelopes cannot carry raw object bytes.
4. A C-STORE callback blocks only its pynetdicom association thread, never the event loop. Success
   is returned only after required object/ring writes and required event admission complete.
5. Thread ingress has a finite capacity and finite wait timeout. Saturation/timeout is a visible
   failure, not a drop. Recommended C-STORE status mapping:
   - malformed/missing required dataset data: `0xC210` (cannot understand);
   - durable storage or ingress resource exhaustion: `0xA700`;
   - unexpected processing failure: `0xC211`.
   Verify status meanings against the locked pynetdicom/pydicom documentation before acceptance.
6. Non-C-STORE observations may complete asynchronously only when every future is observed and a
   failure increments a named diagnostic counter.
7. Shutdown closes listener admission first, drains active associations and admitted thread work,
   then drains capture/event persistence. Deadline expiry interrupts active sessions explicitly.
8. Repeated stop/interrupt is idempotent. A late callback receives a refusal and cannot write into a
   sealed package.

Acceptance:

- ADR is Accepted, indexed, and consistent with ADR-0002, ADR-0017, and ADR-0022;
- no production code lands in this commit.

Commit: `docs(adr): ratify capture ingress ownership and saturation`

### PRC-002 - Ratify measurable performance closure gates

**Priority:** P0  
**Files:** next available ADR number; `docs/adr/README.md`;
`docs/planning/phase-18-performance-report.md`

ADR-0030 ratifies volume/retention but intentionally does not ratify latency. Create `ADR-0037` if
that number remains available; otherwise use the next unallocated number and update all plan
references. Use structural gates as blocking CI checks and timing as release evidence on an
identified reference machine.

Required workloads and proposed gates:

| Dimension | Release workload | Blocking structural gate | Proposed reference target |
|---|---|---|---|
| Collection page | 10,000 captures, 100,000 instances, 500,000 events; page sizes 50 and 500; first/middle/final page | At most count + page query for simple projections; at most count + capture page + attached object query for captures; returned rows bounded by page and page-owned children; zero filesystem stats/opens | p95 <= 250 ms/page on local SSD reference host |
| Sort/filter page | Same database; every public sort/filter field | Filtering/sorting occurs in SQL; deterministic unique tie-breaker; no full tuple materialization | p95 <= 500 ms/page on reference host |
| Full rebuild | 10,000 capture manifests, 100,000 instances, representative events | Study/series projection rebuild exactly once; SQL work grows linearly; no ready state before completion | <= 60 s on local SSD reference host |
| Rebuild scaling | N and 2N deterministic workloads | projection-rebuild count remains one; SQL statement count and bytes processed do not show quadratic growth | 2N median <= 3x N median |
| Ring steady state | Segment-filled retained set, then at least 10 segment turnovers | eviction bytes written do not depend on total retained bytes; no full retained-set rewrite | write amplification <= 4x newly accepted persisted bytes after warm-up |

The ADR must name hardware/filesystem identity, sample count, warm-up, median/p95 method, and noise
policy. Generic hosted-runner timings remain informational. Structural gates run on every PR.

Acceptance:

- thresholds are accepted before optimization is claimed successful;
- ADR distinguishes ADR-0030 hard volume gates from new operational performance gates;
- no result is backfilled before measurement.

Commit: `docs(adr): ratify release closure performance gates`

## 6. Work Package 1 - Concurrency and Saturation

### PRC-100 - Make thread-ingress outcomes explicit

**Priority:** P0  
**Depends on:** PRC-001  
**Files:** `src/lumora_probe/core/bus.py`, `src/lumora_probe/core/config.py`, core tests,
generated config/operator docs only when public configuration changes

Steps:

1. Keep the existing bounded semaphore; do not add a second unbounded queue.
2. Replace generic threaded-ingress `RuntimeError` outcomes with structured, distinguishable
   errors for not-started, shutting-down, saturated, cancelled, and timed-out admission.
3. Expose an immutable ingress snapshot containing capacity, current pending count, saturation
   refusals, completion failures, cancellations, and timeouts. Counters must be lock-safe.
4. Define one bounded wait timeout for DICOM-required event admission. If operator configurable,
   place it in immutable startup config with explicit env/file provenance and validation. If fixed,
   state the reason in the ADR and one named constant.
5. On timeout, cancel the submitted future where possible and ensure the semaphore permit is
   released exactly once, including immediate scheduling failure and cancellation races.
6. During EventBus shutdown, reject new threaded ingress before queue drain and wait for already
   admitted submissions. Do not auto-start a stopped bus from a late callback.

Tests:

- capacity never exceeds the configured value under 100+ simultaneous producer threads;
- exactly one permit is released for success, validation failure, cancellation, timeout, and loop
  shutdown;
- pending count returns to zero after each scenario;
- submissions after shutdown fail immediately;
- accepted capture-channel events remain gap-free and no accepted future is left unresolved.

Acceptance:

- no unbounded scheduled coroutine/future growth;
- all rejection categories are observable and deterministic;
- existing UI dropping behavior is unchanged.

Commit: `fix(core): make threaded event ingress outcomes explicit`

### PRC-101 - Enforce capture writer transition ownership

**Priority:** P0  
**Depends on:** PRC-100  
**Files:** `src/lumora_probe/captures/service.py`, `src/lumora_probe/captures/format.py` only if
writer state guards are absent, capture component tests

Steps:

1. Audit every access to `_sessions`, `Capture`, and `CapturePackageWriter`; make each conform to
   the accepted lock protocol.
2. Introduce explicit internal session states (`accepting`, `stopping`, `sealed`, `interrupted`) or
   reuse domain state when it can atomically guard admission. Do not create a second competing state
   machine.
3. Mark a session non-accepting while holding the session lock before stop/interrupt publishes
   lifecycle events. Late PDU/object/event callbacks must skip/refuse that session, never append.
4. Keep expensive serialization outside the session lock when safe; re-check state under the lock
   immediately before durable append.
5. Ensure ring append and active-session append have an explicit outcome. A partial success must be
   diagnosed; C-STORE cannot report success when required active-capture persistence failed.
6. Convert broad persistence swallowing in `_record_event()` into a visible failure state. The bus
   subscriber must not claim delivery while every active package append failed.
7. Make stop, interrupt, and engine stop idempotent and safe when invoked concurrently.
8. Preserve manifest digests, object inventories, client-asserted counts, sequence ordering, and
   package recovery behavior.

Adversarial component tests:

- 8-16 producer threads append unique synthetic objects and PDUs while one loop task stops capture;
- event consumer append overlaps object append and stop;
- stop and interrupt race each other;
- callback arrives after seal and after session removal;
- writer raises `OSError` during object, event, manifest, and seal operations;
- each successful object appears exactly once by digest; manifest state is completed or interrupted,
  never running; JSONL files contain complete lines only.

Use barriers/events, not sleeps, to force interleavings. Repeat the core race enough times to expose
ordering defects while keeping the test deterministic.

Acceptance:

- ThreadSanitizer is not available for Python; test assertions and lock ownership are the proof;
- no dictionary mutation, write-after-seal, torn JSONL, or silent persistence failure;
- golden capture bytes remain unchanged where behavior is unchanged.

Commit: `fix(captures): enforce writer ownership across callback transitions`

### PRC-102 - Map DICOM saturation and persistence failures to protocol outcomes

**Priority:** P0  
**Depends on:** PRC-101  
**Files:** `src/lumora_probe/associations/network.py`, association contracts if necessary,
`src/lumora_probe/bootstrap.py`, DICOM component tests

Steps:

1. Give C-STORE a single ordered execution contract: validate/encode dataset, durably retain
   required bytes, admit required observed events, then return success.
2. Wait for required event futures with the PRC-100 timeout from the association thread. Never call
   blocking `Future.result()` on the event loop.
3. Map malformed data, resource exhaustion/saturation, and internal failure to the statuses ratified
   in PRC-001. Centralize constants and diagnostic names; do not scatter hexadecimal literals.
4. Count ingress saturation, timeout, completion error, C-STORE persistence failure, and late
   callback refusal separately. Surface totals through existing health/metric adapters without
   logging patient attributes or object bytes.
5. Make listener drain wait for active association threads and pending admitted event futures. A
   single `join(timeout=0.1)` pass is not sufficient evidence of drain.
6. Ensure listener admission closes before drain. New associations during draining must be refused.
7. Observe every fire-and-observe association event future. Avoid callbacks that raise into
   pynetdicom without a corresponding diagnostic.

Tests:

- real loopback C-STORE receives success only after a blocking test sink is released;
- saturated event ingress returns the ratified failure status within the bounded timeout;
- disk/persistence failure returns a failure status and increments the exact counter;
- malformed dataset status differs from resource exhaustion;
- active association drain completes when work completes and remains pending while a barrier is held;
- callback after stop is refused and cannot mutate capture state.

Acceptance:

- successful C-STORE means the required local durable path completed;
- no capture event is silently dropped due to thread saturation;
- readiness/health detail gives operators a cause without sensitive content.

Commit: `fix(dicom): propagate ingress saturation and persistence failures`

### PRC-103 - Add integrated adversarial saturation suite

**Priority:** P0  
**Depends on:** PRC-102  
**Files:** new `tests/test_production_concurrency.py` or narrowly named equivalent

Scenarios:

1. Multiple simultaneous associations each send unique SOP Instance UIDs into one running process.
2. Configure small ingress limits and hold the capture subscriber with a deterministic barrier.
3. Fill admission exactly to capacity; verify further C-STORE requests fail explicitly.
4. Release the barrier; verify admitted requests finish, pending count reaches zero, and recovery is
   possible.
5. Repeat while stopping an explicit capture session through the test composition handle.
6. Repeat while listener admission closes.
7. Verify event sequence has no gaps among accepted events, capture JSONL has complete records, all
   successful SOP UIDs are in durable object inventory, and failed SOP UIDs are not claimed as
   successfully persisted.
8. Record peak pending submissions and prove it never exceeds capacity.

Do not use arbitrary sleeps for orchestration. Use barriers, futures, listener readiness, and
bounded polling only at the process/network boundary.

Acceptance:

- scenarios pass repeatedly (`pytest --count` may be used locally but must not add a dependency);
- test timeout produces a useful failure rather than hanging CI;
- tests carry `component`, `dicom`, and `slow` markers as appropriate.

Commit: `test(concurrency): cover DICOM ingress and capture saturation`

## 7. Work Package 2 - Process Shutdown Under Traffic

### PRC-200 - Expose a narrow production runtime test handle

**Priority:** P1  
**Depends on:** PRC-103  
**Files:** `src/lumora_probe/bootstrap.py`, `tests/test_bootstrap.py`

The forced-deadline process test needs deterministic control of the real graph without production
test environment variables or private lifecycle list access.

Steps:

1. Extract a small internal `ProductionRuntime` result from composition containing the ASGI app and
   named handles already stored in `app.state` (lifecycle, capture engine, listener, bus, paths).
2. Keep `build_production_app(config)` unchanged as the public production entry and make it return
   `build_production_runtime(config).app`.
3. Do not add runtime behavior switches, hidden HTTP routes, or environment-only fault injection.
4. Keep concrete cross-slice wiring in bootstrap.

Acceptance:

- shipped CLI still calls `build_production_app()`;
- normal production graph is byte-for-byte equivalent in dependencies/configuration;
- tests can wrap a public lifecycle method on a specific runtime instance before starting Uvicorn.

Commit: `refactor(bootstrap): expose composed runtime for process verification`

### PRC-201 - Verify graceful SIGTERM during sustained DICOM traffic

**Priority:** P0  
**Depends on:** PRC-200  
**Files:** `tests/test_production_composition.py`, shared process helpers under `tests/`

Steps:

1. Split existing process startup/stop helpers into a reusable helper with captured stdout/stderr,
   bounded readiness polling, and guaranteed kill cleanup.
2. Start the shipping `uv run lumora serve` entry with isolated ports/data root.
3. Run several SCU workers sending unique synthetic instances continuously. Track every C-STORE
   response and SOP UID.
4. After a deterministic minimum number of successes and at least one active association, send
   SIGTERM on POSIX. This test is POSIX process-signal evidence; Windows installed-artifact smoke is
   handled separately.
5. Verify new associations stop being accepted, admitted work drains, and process exits inside
   `shutdown_grace_seconds` plus a small harness allowance.
6. Restart with the same data root, promote the retained ring window, and verify every acknowledged
   success is represented by durable object evidence/projection. Failed or interrupted requests
   must not be reported as successful.
7. Parse persisted ring/capture JSONL and assert no torn trailing line.

Acceptance:

- process exits without kill fallback;
- no manifest remains `created`, `running`, or `stopping`;
- every successful C-STORE has durable evidence after restart;
- stderr contains no unhandled task/future exception.

Commit: `test(acceptance): cover graceful shutdown during active traffic`

### PRC-202 - Verify forced deadline and explicit interruption

**Priority:** P0  
**Depends on:** PRC-201  
**Files:** process test harness, `tests/test_production_composition.py`; source only if a real defect
is exposed

Steps:

1. In a child-process test harness, build the same `ProductionRuntime` used by the CLI.
2. Start one explicit capture session through the runtime handle and admit synthetic DICOM traffic.
3. Wrap capture drain with a deterministic barrier that restores the original drain when cancelled.
   This is test code, not a production switch.
4. Configure a short shutdown grace, signal the child, and hold the barrier through deadline expiry.
5. Assert lifecycle invokes interrupt, seals the active package as `interrupted`, records a
   non-empty reason, and allows the process to exit.
6. Restart through the unmodified shipping CLI. Verify recovery indexes the interrupted package and
   readiness reports the normal service graph.
7. Verify repeated cleanup/interrupt causes no second seal or manifest corruption.

Acceptance:

- deadline path is observed at a real process boundary;
- forced shutdown leaves explicit interrupted evidence, never a falsely completed capture;
- child always exits or the harness kills it and fails with logs;
- restart recovery passes.

Commit: `test(acceptance): cover forced shutdown deadline recovery`

## 8. Work Package 3 - Performance Closure

### PRC-300 - Build deterministic benchmark fixtures and measurement report

**Priority:** P0  
**Depends on:** PRC-002 and Work Package 2  
**Files:** new `tests/performance/` helpers or existing Phase 18 modules;
`docs/planning/phase-18-performance-report.md`

Steps:

1. Generate synthetic manifests/index rows directly where disk object contents are irrelevant.
   Generate real capture directories only for rebuild measurements.
2. Use fixed UID/capture seeds. Do not commit generated large databases or DICOM files.
3. Record workload counts, total bytes, filesystem type, Python/SQLite versions, CPU, memory, and
   commit.
4. Separate correctness assertions from elapsed-time reporting. Structural assertions block PRs;
   reference timing runs block release promotion.
5. Run at least one warm-up and five measured samples; report median and p95 without deleting slow
   outliers.
6. Capture SQL statement counts with SQLite trace/progress hooks and filesystem stat/open/rewrite
   bytes with narrow injectable observers. Do not monkeypatch global stdlib behavior across tests.
7. Commit the pre-optimization baseline to the report before performance changes.

Acceptance:

- fixtures are reproducible and bounded in CI runtime/disk;
- report clearly labels baseline misses;
- no invented pass claim where only measurement exists.

Commit: `test(performance): establish release closure workloads`

### PRC-301 - Complete bounded repository pagination

**Priority:** P1  
**Depends on:** PRC-300  
**Files:** slice `contracts.py` as needed, capture/study repositories, web query/pagination adapters,
bootstrap adapters, API tests, OpenAPI artifact only if contract changes

Steps:

1. Replace optional `getattr(list_page)` behavior in production with an explicit page-query
   protocol. Keep the in-memory adapter for tests but make production conformance statically
   checkable.
2. Define validated query objects containing resource, page/limit, supported sort specs, supported
   filter expression, and deterministic tie-breaker.
3. Translate only whitelisted sort/filter fields to parameterized SQL. Never interpolate user
   values or unvalidated identifiers.
4. Add stable indexes matching each default and supported sort/filter path. Review with
   `EXPLAIN QUERY PLAN`; do not add redundant indexes blindly.
5. Make capture point lookup query one capture and its objects by ID. Make study/series/instance/event
   point lookup use direct `WHERE` queries.
6. Keep public page/page_size response shape unless a contract change is deliberately approved.
7. For capture pages, fetch only objects belonging to captures on that page. Preserve persisted
   object sizes and prohibit filesystem `stat` during list/get requests.
8. Define stable behavior under inserts between page requests. With the existing page-number API,
   require deterministic ordering and document that offset pagination may shift under concurrent
   inserts; do not silently introduce cursor pagination.

Tests:

- first, middle, final, and beyond-final page at release workload;
- every supported ascending/descending sort and exact/text filter;
- duplicate primary sort values use a unique tie-breaker;
- SQL injection strings remain values and do not alter queries;
- query count/row count and no-filesystem-access gates from PRC-002;
- response/OpenAPI compatibility.

Acceptance:

- structural and reference targets pass;
- no production list/get path materializes the full resource merely to return one page/item.

Commit: `perf(storage): bound projection and capture pagination`

### PRC-302 - Prove linear, failure-safe index rebuild

**Priority:** P1  
**Depends on:** PRC-300  
**Files:** `src/lumora_probe/captures/repository.py`, `src/lumora_probe/core/storage.py`, recovery
adapter, rebuild/performance tests

Steps:

1. Assert full rebuild calls study/series projection recomputation exactly once after all valid
   capture/instance/event rows are indexed.
2. Measure N and 2N SQL statement count, row count, bytes, and elapsed time.
3. Keep invalid packages as degraded diagnostics while indexing valid authoritative packages.
4. Define current-process atomicity: readiness remains false until schema, all valid captures, and
   final projections finish. Any unexpected rebuild failure aborts startup.
5. Test process interruption at early, middle, and final rebuild barriers. On next start, recreate
   derived `index.db` and converge to the same `projection_snapshot()` as a clean rebuild.
6. If per-capture transactions dominate the ratified target, batch a bounded number of captures per
   transaction. Never require all repository contents in memory and never weaken package
   verification.
7. Emit discovered/indexed/skipped counts and duration through existing health/logging, with paths
   redacted to the offending package only.

Acceptance:

- exactly one final projection rebuild;
- N/2N structural scaling and accepted reference timing pass;
- no ready response over partial current-process projections;
- crash/restart converges byte-for-byte.

Commit: `perf(storage): prove linear recoverable index rebuilds`

### PRC-303 - Replace whole-file ring expiry with bounded segments

**Priority:** P1  
**Depends on:** PRC-300  
**Files:** `src/lumora_probe/captures/service.py` or a narrowly owned captures repository module,
ring tests, migration/recovery tests, operator/upgrade docs later in PRC-700

Only execute the storage redesign after the baseline demonstrates the current full rewrite misses
the accepted structural gate. The current algorithm is expected to miss because one eviction calls
`_rewrite()` over every retained record.

Required design:

1. Persist append-only bounded segments under the ring root plus atomic metadata identifying active
   and retained segments. Use a next available internal format version.
2. Choose and ratify a segment target (recommended 8 MiB). A single record larger than the target
   occupies its own bounded segment and still counts against the hard ring cap.
3. Append and fsync the active segment according to current durability semantics. Rotate by size;
   atomically publish metadata after segment durability.
4. Evict complete expired/over-cap segments by unlinking them. Compact at most one boundary segment
   when record-level retention requires it. One eviction must never rewrite all retained segments.
5. Preserve insertion order, record kind, raw bytes, occurrence/recorded timestamps, aggregate ID,
   metadata, status counts, and promotion-window selection.
6. Avoid retaining a second base64 copy of the full 2 GiB cap in memory. Keep lightweight record
   metadata/references and load raw segment content only for promotion/read paths where practical.
7. Recover complete records after torn active-segment tail, stale temporary metadata, missing final
   metadata rename, and process death during rotation/eviction.
8. Read the legacy `records.jsonl`. Migrate atomically on first successful start or retain a
   read-compatible path until the next successful compaction. Never delete the legacy file before
   new metadata/segments are durable.
9. Refuse unknown newer ring format versions with a structured recovery error.

Tests:

- segment rotation and exact ordered snapshot;
- retention-time and byte-cap eviction;
- oversized single record;
- torn tail, interrupted rotation, interrupted metadata rename, and stale temp cleanup;
- legacy migration with before/after snapshot equality;
- promotion produces the same manifest/object/event evidence as legacy persistence;
- rewrite/write-amplification counter passes PRC-002 across 10+ turnovers;
- restart RSS and retained-byte accounting remain bounded and honest.

Acceptance:

- eviction cost is bounded by one segment/metadata operation, independent of total retained bytes;
- ADR-0030 30-minute/2-GiB semantics and no-silent-drop gate still pass;
- migration and rollback instructions are documented before release.

Commit: `perf(captures): segment persisted ring-buffer expiry`

### PRC-304 - Publish performance evidence

**Priority:** P0  
**Depends on:** PRC-301 through PRC-303

Update the Phase 18 performance report with before/after samples, workload identity, structural
counts, timing distributions, write amplification, peak RSS, and result against each ratified gate.
Link raw CI artifacts. Keep unresolved dimensions marked open.

Commit: `docs(performance): record release closure measurements`

## 9. Work Package 4 - Strict Type Expansion

### Rules for every typing task

1. Run strict BasedPyright on the target slice before edits and preserve diagnostics in the PR.
2. Fix contracts at ownership boundaries first: concrete return types, Protocol members, typed
   Pydantic payload validation, and narrow `cast()` only after runtime validation.
3. Keep framework route-function unused ignores narrow until BasedPyright supports decorator usage.
4. For untyped third-party pydicom/pynetdicom values, isolate `Any` in association/decode adapter
   boundaries; do not leak it into domain/service contracts.
5. Add runtime tests where a type fix changes validation or branching.
6. Each slice commit must pass its strict check, affected tests, Ruff, and import-linter.

### PRC-400 - Add already-clean slices to the canonical gate

Add `analysis`, `plugins`, and `bootstrap.py` to pyproject/CI strict checking first. Use one canonical
command in local docs and CI. Do not rely on command-line paths that differ from pyproject include.

Commit: `ci(types): gate clean application slices`

### PRC-401 - Type associations and settings

Resolve the current 3 association and 6 settings errors. Expected focus: partially typed pydicom
calls, relay generator outcomes, unknown setting names, and class-level Pydantic `model_fields`.
Add both slices to the canonical gate.

Commit: `refactor(types): type associations and settings slices`

### PRC-402 - Type replay and studies

Resolve the current 11 errors in each slice. Remove impossible `None`/`isinstance` branches only
after tests prove runtime contracts. Type SQLite rows at repository mapping boundaries. Add both
slices to the canonical gate.

Commit: `refactor(types): type replay and studies slices`

### PRC-403 - Type captures

Resolve the current 15 errors after concurrency/ring changes stabilize. Expand
`CaptureEventIngress` with the exact subscribe/drain members actually required or split publish and
subscription protocols. Type pydicom serialization at one adapter. Add captures to the gate.

Commit: `refactor(types): type captures slice`

### PRC-404 - Type web

Resolve the current 27 errors after pagination contracts stabilize. Replace dynamic provider
`getattr` checks where production now has explicit protocols. Keep test factory optional providers
without weakening production composition validation. Add web to the gate.

Commit: `refactor(types): type web adapters`

### PRC-405 - Type reports and close whole-package strict mode

Resolve the current 76 report errors in small internal edits but one reports-owned commit. Validate
decoded JSON mappings before indexing/getting fields; introduce typed report DTOs only where they
remove repeated unknown-data checks. Then set BasedPyright include to all `src/lumora_probe` and make
CI run `uv run basedpyright` with no narrower path arguments.

Acceptance for Work Package 4:

- `uv run basedpyright` reports zero errors across every `lumora_probe` slice and bootstrap;
- no excluded application files, downgraded strictness, blanket ignore, or new architecture breach;
- mandatory runtime suite remains green.

Commit: `refactor(types): type reports and gate lumora_probe`

## 10. Work Package 5 - Compatibility Warning Closure

### PRC-500 - Modernize synthetic DICOM construction and writes

**Priority:** P1  
**Files:** warning-producing tests, fixture generator, relevant lite/common adapters if warning
traces identify production calls

Steps:

1. Replace `write_like_original` with `enforce_file_format` or explicit modern pydicom write
   parameters while preserving each test's intended valid/malformed file shape.
2. Stop assigning `is_little_endian`/`is_implicit_VR`; set `file_meta.TransferSyntaxUID` and pass
   explicit writer arguments where deliberately constructing unusual data.
3. Replace unknown `MediaStorageApplicationTitle` with the correct DICOM file-meta keyword required
   by the test, expected to be `SourceApplicationEntityTitle`; verify against pydicom's dictionary.
4. For malformed-file tests, build malformed bytes deliberately rather than relying on deprecated
   writer compatibility behavior.
5. Wrap the one intentionally invalid IS construction in `pytest.warns()` with exact category and
   message, proving the warning is expected.
6. Regenerate committed synthetic fixtures only if fixture bytes are intentionally changed. Review
   every binary diff and verify UIDs/patient values remain synthetic.

Acceptance:

- pydicom deprecation and unknown-keyword warnings are zero;
- negative tests still exercise the same malformed conditions;
- golden capture/package comparisons pass or receive an explicitly reviewed fixture update.

Commit: `test(dicom): migrate synthetic fixtures to current pydicom APIs`

### PRC-501 - Resolve Starlette TestClient transport warning

**Priority:** P1  
**Files:** `pyproject.toml`, `uv.lock`, TestClient imports only if needed

Preferred minimal path: add the Starlette-supported `httpx2` test dependency while retaining
`httpx` for existing ASGI/process clients. Verify FastAPI TestClient behavior on all three OSes. If
the packages conflict or the API is incompatible, migrate HTTP-only tests to `httpx.AsyncClient`
with `ASGITransport`; retain TestClient only for WebSocket tests and document the supported
transport dependency.

Do not silence `StarletteDeprecationWarning`.

Acceptance:

- no warning on TestClient import/creation;
- HTTP lifespan and WebSocket tests still exercise startup/shutdown;
- lockfile changes contain only intended dependency resolution.

Commit: `test(web): use supported Starlette test transport`

### PRC-502 - Turn unexpected warnings into failures

Add pytest warning policy after PRC-500/501. Default to `error`. Add only exact, documented filters
for unavoidable warnings owned by locked upstream dependencies, each with issue URL, package
version, removal condition, and dedicated compatibility test. Prefer no filters.

Run the full suite in a fresh locked environment to avoid import-cache hiding.

Acceptance:

- default suite passes with zero unexpected warnings;
- intentional warning tests use local `pytest.warns()`;
- CI cannot regress silently.

Commit: `ci(test): fail on unexpected compatibility warnings`

## 11. Work Package 6 - Cross-OS Installed-Artifact Verification

### PRC-600 - Add artifact-isolated production smoke driver

**Priority:** P0  
**Files:** `scripts/smoke_installed_distribution.py` or a narrowly named test support script;
packaging tests

The driver must run outside the repository working directory using the target virtual environment's
Python. It must assert imported module paths come from site-packages, not `src/`.

For each artifact:

1. create a fresh virtual environment;
2. install exactly one wheel or sdist plus its declared dependencies, without editable install;
3. clear `PYTHONPATH` and run from a temporary directory;
4. verify `lumora_probe`, all four shared/lite packages, templates, static CSS/JS, and vendor
   manifest import/read from the installed distribution;
5. launch `python -m lumora_probe.cli serve` with isolated data/ports;
6. wait for named HTTP readiness services and open DICOM TCP listener;
7. send synthetic C-ECHO and C-STORE;
8. promote ring evidence and verify capture/instance API visibility;
9. stop the process using the best platform-supported mechanism, with kill fallback treated as test
   cleanup rather than graceful-shutdown evidence;
10. retain stdout/stderr and installed package metadata on failure.

The smoke driver must use stdlib plus packages installed from the artifact. It must not import test
helpers that make the source checkout importable.

Commit: `test(packaging): add installed production smoke driver`

### PRC-601 - Gate wheel and sdist on Linux, macOS, and Windows

**Priority:** P0  
**Files:** `.github/workflows/ci.yml`

Add a required matrix job:

- OS: `ubuntu-latest`, `macos-latest`, `windows-latest`;
- artifact: `wheel`, `sdist`;
- Python: 3.13;
- six independent combinations, `fail-fast: false`.

Each job must build from the checked-out commit, create a clean venv, install the selected artifact,
run PRC-600, and upload logs/package inventory on failure. Do not reuse the repository's synced dev
environment as installation proof. Use platform-neutral Python path discovery; do not assume
`bin/` on Windows.

Keep the existing source quality matrix and scheduled interop job. Installed smoke becomes a
required PR/release check, not schedule-only evidence.

Acceptance:

- all six combinations pass in GitHub Actions;
- wheel and sdist are each tested on every declared OS;
- source checkout shadowing assertion passes;
- artifacts/logs are retained long enough for release review.

Commit: `ci(packaging): gate installed artifacts across supported OSes`

## 12. Work Package 7 - Release Reconciliation

### PRC-700 - Reconcile operations and compatibility documentation

**Priority:** P0  
**Depends on:** all prior work packages  
**Files:** README, operator guide, troubleshooting, upgrade/migration, known limitations, release
notes, ADR index, original readiness audit

Update only verified claims:

1. document normal drain order, shutdown grace, forced interruption state, and restart recovery;
2. document DICOM saturation/failure statuses and the health counters operators should inspect;
3. document ring segment layout, migration, disk/RSS sizing, rollback, and newer-format refusal;
4. document pagination/rebuild release workload and link performance report; do not generalize local
   SSD results to network filesystems, which remain refused;
5. document warning policy and supported locked dependency line;
6. document wheel/sdist OS matrix with CI run/artifact links;
7. update known limitations for anything measured but not ratified;
8. update the original readiness audit checklist only after evidence exists. Keep original finding
   history; add closure references rather than rewriting discovery facts;
9. confirm no real/de-identified patient data entered any commit.

Acceptance:

- README, guides, release notes, audit status, and `CLAUDE.md` make consistent claims;
- every checked audit box links to a test, report, ADR, or CI run;
- unresolved items remain unchecked and named.

Commit: `docs(release): reconcile production readiness evidence`

### PRC-701 - Run final release gate and evidence audit

No code changes in this task unless a failure produces a new separately scoped fix commit.

Run from a clean checkout:

```console
uv sync --locked
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run lint-imports --no-cache
uv run basedpyright
npm ci
npm run check:assets
git diff --check
```

Also require:

- structural performance suite;
- reference performance report against accepted gates;
- graceful and forced process tests;
- six installed-artifact CI matrix results;
- scheduled DCMTK/dcm4che/Orthanc interop result at the release commit;
- exported-lock dependency audit artifact;
- zero unexpected warnings;
- clean worktree after generated-artifact checks.

Acceptance:

- all gates pass at one commit SHA;
- skipped tests are enumerated and each is opt-in external/browser coverage, not a release gate;
- release evidence records exact commit and CI run IDs.

Commit: none unless evidence-only documentation needs a final atomic update:
`docs(audit): record final production readiness closure`

## 13. Dependency and Commit Order

Execute in this exact order unless a documented replan changes it:

1. PRC-001 capture ownership ADR
2. PRC-002 performance gate ADR
3. PRC-100 thread ingress outcomes
4. PRC-101 capture ownership
5. PRC-102 DICOM outcomes
6. PRC-103 saturation suite
7. PRC-200 runtime test handle
8. PRC-201 graceful active-traffic shutdown
9. PRC-202 forced deadline recovery
10. PRC-300 benchmark baseline
11. PRC-301 pagination
12. PRC-302 rebuild
13. PRC-303 ring segmentation, only after measured gate failure
14. PRC-304 performance report
15. PRC-400 through PRC-405 typing expansion
16. PRC-500 through PRC-502 warning closure
17. PRC-600 and PRC-601 installed artifacts
18. PRC-700 documentation
19. PRC-701 final gate

After each production-code commit, run affected tests, Ruff, import-linter, and the currently active
BasedPyright gate. After each work package, run the full suite. Never postpone all verification to
the end.

## 14. Failure and Replan Rules

1. If concurrency remediation requires moving raw fidelity data through EventBus, stop: that
   conflicts with the selected design and needs ADR reconsideration.
2. If a successful C-STORE cannot be tied to durable evidence, do not weaken acceptance; return a
   failure status and fix the persistence path.
3. If normal SIGTERM requires kill fallback, Work Package 2 is failed even if restart recovers.
4. If forced interruption cannot exit after lifecycle timeout, preserve artifacts/logs and fix
   unwind ordering before performance work.
5. If pagination timing misses but structural gates pass, profile SQL and serialization before
   adding caches. `index.db` is rebuildable; do not add a second authoritative store.
6. If ring segmentation changes capture package bytes, stop. Ring persistence is internal and must
   not alter `.lpcap` format without a separate ADR/version change.
7. If strict typing exposes a real runtime ambiguity, add a failing runtime test before fixing it.
8. If zero warnings requires an incompatible major dependency upgrade, do not force it into this
   plan. Record a targeted upstream-owned warning with removal criteria or write a separate upgrade
   ADR/plan.
9. If one OS fails only due to process-control semantics, adjust the smoke harness; do not remove the
   declared OS classifier without a release decision.
10. Any API/event schema change requires generated OpenAPI/event catalog regeneration and a
    compatibility note in the same atomic commit.

## 15. Completion Checklist

- [ ] Capture ownership/backpressure ADR accepted.
- [ ] Performance-gate ADR accepted.
- [ ] Pending threaded submissions are bounded, classified, and observable.
- [ ] Capture writer transitions are race-safe and adversarially tested.
- [ ] DICOM saturation/persistence failures return explicit statuses.
- [ ] Graceful SIGTERM passes during sustained real DICOM traffic.
- [ ] Forced process deadline leaves an interrupted package and restart recovers it.
- [ ] Pagination structural and reference gates pass.
- [ ] Full rebuild structural and reference gates pass.
- [ ] Ring expiry meets bounded write-amplification gate; segmentation/migration passes if needed.
- [ ] `uv run basedpyright` covers all `src/lumora_probe` with zero errors.
- [ ] Default test suite has zero unexpected warnings.
- [ ] Wheel and sdist production smoke pass on Linux, macOS, and Windows.
- [ ] External interop and dependency audit pass at release commit.
- [ ] Documentation claims match recorded evidence.
- [ ] No production route advertises a required capability through an empty/null provider.
- [ ] No real or de-identified patient data was introduced.
- [ ] Final worktree and generated artifacts are clean.
