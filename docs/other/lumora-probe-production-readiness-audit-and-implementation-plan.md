# Lumora Probe Production-Readiness Audit and Implementation Plan

**Status:** Production-readiness release closure verified on August 1, 2026; historical findings and intentional v1 limitations remain recorded below
**Audit snapshot:** findings discovered at `b3f6b24`; source revalidated at `25351b4`; final docs-only HEAD `11dd9ee` (`master`)  
**Audit date:** 2026-08-01  
**Closure evidence:** implementation SHA `05474d5`; hosted CI run `30716410290`; benchmark `docs/planning/phase-18-release-closure-benchmark-2026-08-01.json`
**Audience:** implementation agent with limited repository context  
**Scope:** `src/lumora_probe/`, production composition, shared packaging/CI seams, and their tests/docs  
**Out of scope for the original audit:** changing accepted product scope and replacing the existing
`docs/other/cross-product-sharing-audit-and-refactoring-plan.md`

## Implementation checkpoint — August 1, 2026

The current worktree now composes the production service graph: event bus, bounded executor,
index recovery, capture/ring-buffer engine, DICOM listener, durable operations/jobs, study
projections, frame decoding, metadata inspection, reports, transfer inspection, runtime settings,
and health probes. Startup recovery preserves valid captures while reporting invalid packages as
degraded diagnostics. Additional hardening covers archive limits, plugin install containment,
IPv6 Host parsing, event-bus shutdown admission, persisted object sizes, and direct-sqlite
architecture ratification in ADR-0035.

Verified in the current worktree: full pytest (`540 passed, 17 skipped`), Ruff check/format,
import-linter, strict BasedPyright for `core`/`shared` plus the production bootstrap, asset drift
checks, process-boundary DICOM/C-STORE/restart smoke, and isolated wheel/sdist import/template
smoke. The release-closure work described below subsequently supplied the adversarial shutdown/process
evidence, whole-package typing, reference benchmark, final-SHA interoperability, and reconciled
release documentation. Historical checkpoint wording is retained to preserve finding provenance.

> **Snapshot warning:** unrelated work changed concurrently while this audit ran. Commits `447f635`
> and `25351b4` added a `CaptureEngine`, `CaptureRepository`, and `LifecycleManager` to bootstrap
> after initial evidence collection; `11dd9ee` then marked the narrow lifecycle plan complete. This
> plan was updated for that partial remediation. Before
> implementation, rebase onto current HEAD and revalidate every finding. Do not discard unrelated
> worktree changes.

## 1. Executive summary

The audit identified a hollow production composition, destructive derived-index startup,
false-positive readiness, non-persistent runtime settings, host-policy mismatch, unsafe plugin
installation, and ignored executor sizing. The current worktree now composes `lumora serve`
through one lifecycle: bounded executor, index recovery, capture/ring buffer, DICOM listener,
persistent projections, operations/jobs, reports, decode/metadata, transfer inspection, settings,
plugins, and health. A subprocess smoke sends C-ECHO/C-STORE, promotes a capture, observes the
instance through the API, stops by SIGTERM, restarts, and confirms index/settings recovery.

At the original audit checkpoint, production readiness was **not yet release-closed**. The primary
composition blockers and all release-closure gates are now resolved; the evidence ledger below
retains the original finding history and points to the final implementation/CI artifacts.

The following constraints remain intentional: no authentication/RBAC, trusted in-process plugins,
loopback-by-default exposure, single-process operation, and deferred pcap/byte-exact replay,
remote collectors, Prometheus exposition, and PS3.15 de-identification.

No confirmed remote-code-execution vulnerability was found in the HTTP API. No authentication or
RBAC is intentionally provided in v1 under ADR-0009; plugins are intentionally trusted in-process
code under ADR-0021. Those decisions are deployment constraints, not defects. However, the
network trust gate and origin/host mitigations must work as documented before non-loopback use is
safe enough for the accepted trusted-engineering deployment model.

## 2. Evidence and verification

### 2.1 Current snapshot verification

The original audit snapshot predates the current implementation. The current worktree was
revalidated on August 1, 2026; historical commit references below explain finding provenance only:

| Gate | Result | Interpretation |
|---|---|---|
| `uv run ruff check .` | Pass | Lint rules pass. |
| `uv run ruff format --check .` | Pass | Current worktree is formatted. |
| `uv run lint-imports --no-cache` | Pass, 7/7 | Static package boundaries are enforced. |
| `uv run basedpyright src/lumora_probe/core src/lumora_probe/shared` | Pass | Mandatory strict slices pass; bootstrap also passes an incremental strict check. |
| `uv run pytest -q` | `540 passed, 17 skipped` | Full current suite; skips remain opt-in external/browser coverage. |
| affected bootstrap/capture/startup tests | `12 passed` at lifecycle source `25351b4` | New adapter/shutdown tests pass; full suite must still be rerun on the implementation branch. |
| exported-requirements `pip-audit` | Pass | Exported locked requirements audited with `--strict --no-deps --disable-pip`; no known vulnerabilities found. |
| installed-environment `pip-audit --strict` | Inconclusive | It refuses the unpublished local `lumora-probe==0.1.0` package; CI audits the exported lock instead. |

The current exported-lock audit reported no known vulnerabilities. The CI command now uses the
same pinned, project-excluded requirements mode and retains the report artifact.

### 2.2 Runtime smoke evidence

Current process-boundary acceptance (`tests/test_production_composition.py`) verifies:

- readiness exposes event bus, executor, index recovery/database, capture engine, DICOM listener,
  app database, plugin host, and operation jobs;
- the configured DICOM TCP endpoint is open and accepts C-ECHO and synthetic C-STORE;
- ring-buffer promotion creates an indexed capture, the persisted instance is visible through
  `/api/v1/instances`, metadata/report routes return production data, and report jobs complete
  through the durable operation endpoint; hostile HTTP Host headers are rejected;
- SIGTERM exits the process; restart with the same data root rebuilds capture visibility and
  preserves runtime settings provenance;
- wheel and sdist installs import `lumora_probe`/`lumora_dicom_common` and include templates.

Forced shutdown during active traffic is covered by the subprocess test. Configured non-loopback
Host acceptance and hostile Host rejection are also covered. Installed wheel/sdist HTTP+DICOM smoke
is verified separately by the package smoke harness and hosted six-artifact matrix.

### 2.3 Interoperability evidence

`docs/planning/phase-20-interop-results.md` records the final 15-test successful tests against DCMTK,
dcm4che, and Orthanc. The current pinned-container run passed 15 interoperability tests. Both
suites exercise direct listener/relay instances rather than the shipping `lumora serve` composition;
the installed-artifact process smoke is covered separately. The scheduled CI job is blocking for
its selected workflow events.

## 3. Architecture and quality assessment

| Area | Assessment | Evidence / consequence |
|---|---|---|
| Architectural compliance | **Mixed** | Import contracts pass; lifecycle/composition and runtime settings are wired, while DICOM callback ownership remains an explicit follow-up. |
| Implementation correctness | **Substantially remediated** | Production composition, startup recovery, and live settings are implemented; forced-shutdown and scale evidence remain. |
| API design | **Mixed** | Production-required route providers are wired and readiness is honest; test-friendly optional defaults remain by design. |
| Package boundaries | **Structurally good** | 7/7 import-linter contracts pass. Composition adapters must remain in bootstrap/web and use slice contracts. |
| Dependency correctness | **Mixed** | Locking and ranges are reasonable. ADR-0035 ratifies direct `sqlite3`; pydicom v4 deprecations remain. Current vulnerability audit is inconclusive. |
| Layering | **Structurally good** | Domain/framework separation and production composition boundaries pass; residual ownership contract work is documented. |
| Extensibility | **Mixed** | Protocol seams exist, but many are web-owned shapes with no production adapters. Plugin trust model is explicit. |
| Maintainability | **Mixed** | Strong module vocabulary, adapters, and tests; stale phase plans, empty structural stubs, duplicated rule implementations, and compatibility debt remain. |
| Readability | **Generally good** | Small explicit types and structured errors. Composition intent is obscured by optional provider defaults. |
| Testability | **Good, with process coverage added** | 540 tests pass; subprocess DICOM/C-STORE/restart smoke covers the shipping composition. Forced-shutdown and installed-artifact DICOM lanes remain. |
| Performance | **At risk at scale** | Capture paging avoids full object scans; projection/event reads and rebuild/projection/ring write amplification still need budgets and benchmarks. |
| Concurrency | **Needs adversarial evidence** | DICOM callbacks use synchronized capture-engine state and bus thread ingress; saturation and callback-after-shutdown tests remain. |
| Security | **Mixed** | Host/origin/path/SQL controls, plugin containment, and archive bounds are implemented. Non-loopback process acceptance remains pending. No auth is intentional. |
| Resource management | **Improved, still needs adversarial evidence** | Archive bounds, bounded default executor, and lifecycle drain are implemented; forced deadline evidence at process boundary remains. |
| Cross-provider compatibility | **Component-level only** | External DICOM matrix passes direct relay instances, not production composition. |
| Production readiness | **Release closure verified** | Readiness and advertised DICOM/capture workflow are composed; reference gates pass on the documented local host, the six-artifact matrix passes in CI run `30716410290`, and final-SHA interoperability passes in job `91412594111`. |

## 4. Findings register

Severity vocabulary:

- **Critical / P0:** blocks release or all advertised production use.
- **High / P1:** data integrity, security, or major workflow risk; fix in the same remediation cycle.
- **Medium / P2:** correctness, scalability, or maintainability risk with narrower triggers.
- **Low / P3:** debt or hardening; schedule after production contract is restored.

### PR-001 — Production composition is functionally hollow

**Current status:** Resolved in the current worktree; subprocess acceptance covers the composed listener, capture, recovery, API, and job path.

**Severity:** Critical / P0  
**Categories:** incomplete implementation, regression risk, layering, production readiness  
**Files:**

- `src/lumora_probe/bootstrap.py:100-128,131-223` — capture adapter and `build_production_app`
- `src/lumora_probe/web/api.py:178-333` — `create_app` and lifespan
- `src/lumora_probe/cli.py:122-137` — `_run_serve`
- `src/lumora_probe/associations/network.py:441-545` — `DICOMListener`
- `src/lumora_probe/captures/service.py:404-485` — `CaptureEngine`
- `src/lumora_probe/core/lifecycle.py:59-157` — `LifecycleManager`

**Historical root cause:** At the audit snapshot, bootstrap constructed only a partial capture
engine and lifecycle and omitted the listener and production providers.

**Historical impact:** At that snapshot, `lumora serve` could not receive DICOM or expose persisted
capture, instance, report, or operation data despite advertising those capabilities. The current
composition and process acceptance test close this finding.

**Architecture evidence:** ADR-0007 requires one lifecycle manager to own service startup,
reverse shutdown, drain, and health (`docs/adr/ADR-0007-runtime-topology.md:26-35`). Phase 11
explicitly records production capture wiring as unfinished
(`docs/planning/phase-11-completion-report.md:72-87`).

**Required remediation:** Continue beyond the newly added engine/lifecycle wiring and implement
the full production composition in Phase 1 below. Do not count lifecycle registration alone as
completion. The existing `docs/other/lifecycle-manager-wiring-plan.md` is marked complete for its narrow
scope but remains incomplete as a production-composition plan.

### PR-002 — Startup destroys the derived index without rebuilding it

**Current status:** Resolved in the current worktree; recovery diagnostics and restart coverage are present.

**Severity:** Critical / P0  
**Categories:** correctness, startup recovery, data visibility, operational risk  
**Files:**

- `src/lumora_probe/bootstrap.py:131-149`
- `src/lumora_probe/core/storage.py:234-238,354-356`
- `src/lumora_probe/core/storage.py:271-289` — `recreate_index_schema`
- `src/lumora_probe/captures/repository.py:215-227` — `CaptureRepository.rebuild`

**Historical root cause:** The audit snapshot recreated `index.db` without a subsequent authoritative
capture discovery/rebuild.

**Historical impact:** A restart could hide all derived capture, study, instance, and event rows while
evidence remained on disk. The current recovery service rebuilds before readiness and preserves valid
packages while reporting malformed ones.

**Required remediation:** Initialize/migrate `app.db` separately. Rebuild `index.db` exactly once
from all configured capture roots before readiness. Keep readiness false during rebuild. Define
failure policy for one corrupt capture: quarantine/report it without silently publishing a partial
healthy index. Avoid the current double-destruction pattern (`storage.initialise` followed by a
repository rebuild that initializes the index again).

### PR-003 — Readiness reports healthy while required services are absent

**Current status:** Resolved in the current worktree; startup rebuilds the derived index and readiness includes recovery diagnostics.

**Severity:** High / P1  
**Categories:** API correctness, observability, production operations  
**Files:**

- `src/lumora_probe/bootstrap.py:181-187`
- `src/lumora_probe/core/health.py:31-54`
- `src/lumora_probe/web/health_routes.py:28-50`
- `tests/test_phase18_startup.py:23-84`

**Historical root cause:** The audit snapshot registered only a subset of services and did not check
the DICOM port or service set.

**Historical impact:** Supervisors could route traffic to an application incapable of its primary
workflow. The current health registry probes the composed services and process tests assert names
and the open DICOM endpoint.

**Required remediation:** Readiness must include index recovery, event bus, capture engine, DICOM
listener, app/index database query probes, and any runtime required by enabled API capabilities.
Liveness must remain process-health oriented and not fail solely for a recoverable peer condition.

### PR-004 — Production runtime settings are an in-memory test double

**Current status:** Resolved for supported live settings; theme and rule toggles persist as client/UI provenance settings because no server-side analysis runner is enabled in v1.

**Severity:** High / P1  
**Categories:** correctness, architectural drift, API trust, maintainability  
**Files:**

- `src/lumora_probe/bootstrap.py:78-97,209`
- `src/lumora_probe/web/settings_routes.py:21-56`
- `src/lumora_probe/settings/runtime.py:113-266`
- `docs/adr/ADR-0020-configuration-tiers.md:17-50`

**Historical root cause:** The audit snapshot used an in-memory settings provider instead of the
persistent/provenance-aware store.

**Historical impact:** Settings could vanish on restart and silently fail to affect live services.
The current provider persists atomically, preserves source locks, applies supported live targets,
and reports UI-only theme/rule-toggle provenance explicitly.

**Required remediation:** Compose `RuntimeSettingsStore` at `DataPaths.settings`, preserve source
locks, emit `ConfigurationChanged`, persist atomically, and apply each live setting through an
explicit target service. If live application fails, return a structured failure and avoid reporting
success. Startup-only fields must return `RestartRequiredError`.

### SEC-001 — Plugin manifest ID permits destination traversal during install

**Current status:** Resolved in the current worktree with canonical IDs, pre-write containment, temporary copy, validation, and atomic installation.

**Severity:** High / P1  
**Categories:** security, filesystem integrity, input validation  
**Files:**

- `src/lumora_probe/cli.py:148-162`
- `src/lumora_probe/plugins/repository.py:40-46,100-127,150-154`
- `src/lumora_probe/plugins/domain.py:23-49`

**Trigger:** A deliberately selected plugin directory has a manifest ID such as `../outside` or
an absolute/path-like value.

**Root cause:** The manifest validates only that ID is non-empty. `_run_plugin_install` constructs
`destination_root / manifest.plugin_id` and calls `copytree` before `read_manifest(destination)`
checks that the resolved destination is a direct child.

**Impact:** Files can be copied outside `LUMORA_DATA_DIR/plugins` anywhere the process user can
write. The later validation fails but does not remove the already copied tree.

**Required remediation:** Define a canonical plugin-ID grammar (for example reverse-DNS segments),
reject separators, dot segments, drive prefixes, control characters, and reserved names, then
resolve and assert containment **before any write**. Copy to a temporary direct child, validate the
copy, atomically rename, and clean temporary data on every failure. Decide and test symlink policy.
Trusted-code status does not justify an installer path escape.

### SEC-002 — Non-loopback binds remain localhost-only at the request policy

**Current status:** Resolved in the current worktree; startup exposure remains gated, configured allowed hosts are honored, IPv6 parsing is covered, and subprocess configured/hostile Host checks pass.

**Severity:** High / P1  
**Categories:** deployment correctness, security configuration, cross-provider compatibility  
**Files:**

- `src/lumora_probe/bootstrap.py:197-212`
- `src/lumora_probe/core/config.py:28-51,239-255`
- `src/lumora_probe/web/security.py:22-60,87-162`
- `Dockerfile:6-10,28-33`
- `README.md:44-53`

**Trigger:** `--trust-network --host 0.0.0.0`, Docker, a LAN IP, hostname, or reverse proxy.

**Root cause:** Startup correctly gates non-loopback binding, but bootstrap constructs
`SecurityPolicy(read_only=...)` with the default allowlist only: localhost, `127.0.0.1`, and IPv6
loopback. No configured hosts, origins, or trusted proxies can reach production composition.

**Impact:** Documented network/container deployment returns host rejection for legitimate requests.
Operators may be tempted to weaken host checks globally, which would reintroduce DNS-rebinding risk.

**Required remediation:** Add explicit startup configuration for allowed hostnames, allowed origins,
and trusted proxy addresses as ADR-0010 already anticipates. Keep defaults loopback-only. Never infer
trust from arbitrary `X-Forwarded-*` headers and never use `*` as the default host policy. Update
Docker examples to supply the expected external hostname/proxy address.

### CON-001 — DICOM threads directly mutate loop-owned capture state

**Severity:** High / P1  
**Categories:** concurrency, data integrity, resource management  
**Files:**

- `src/lumora_probe/associations/network.py:489-545,689-740`
- `src/lumora_probe/captures/service.py:421-480,538-580,680-758`

**Trigger:** A C-STORE/PDU callback overlaps capture stop, interruption, promotion, or another
association callback.

**Root cause:** Pynetdicom handlers run on association threads. The proposed Phase 11 wiring uses
`CaptureEngine` directly as `c_store_sink` and PDU sink. Those synchronous methods iterate
`_sessions` and write `CapturePackageWriter` objects while loop-side methods mutate `_sessions`,
seal writers, and remove sessions. Only ring-buffer internals have a lock; session/writer ownership
does not.

**Impact:** Possible `dictionary changed size` errors, writes after seal, inconsistent object
inventories, C-STORE failures, lost evidence, or capture corruption. Existing tests call these
paths sequentially and do not exercise overlap.

**Required remediation:** Ratify one ownership mechanism before wiring production. Preserve the
accepted off-bus fidelity path, but add one bounded, drainable thread-to-capture handoff or a fully
specified locking protocol around session and writer transitions. C-STORE must return a status only
after required durability succeeds or fails. Add adversarial tests required by
`docs/planning/07-definition-of-done.md:51-53`.

### CON-002 — Bounded event ingress does not bound pending thread submissions

**Severity:** Medium / P2  
**Categories:** concurrency, scalability, memory exhaustion  
**Files:**

- `src/lumora_probe/core/bus.py:224-265,300-312`
- `src/lumora_probe/associations/network.py:715-740,788-822`

**Trigger:** DICOM threads publish faster than the event loop/capture subscriber drains.

**Root cause:** `publish_from_thread` calls `asyncio.run_coroutine_threadsafe`. The coroutine then
waits on the bounded queue, but callers ignore the returned future. The queue is bounded while the
number of scheduled/waiting coroutine tasks and futures is not.

**Impact:** Sustained load can grow pending tasks/memory despite `ingress_capacity`, and publication
errors are not observed by the producer.

**Required remediation:** Make pending thread submissions bounded and observable. Define whether a
DICOM callback blocks, times out, or returns a DICOM failure when durable ingress is saturated.
Capture traffic must not silently drop. Add saturation, shutdown, and exception-propagation tests.

### CON-003 — Configured executor size has no effect

**Severity:** Medium / P2  
**Categories:** dependency correctness, concurrency, performance, configuration drift  
**Files:**

- `src/lumora_probe/core/config.py:28-44`
- `src/lumora_probe/core/lifecycle.py:179-203` — `ExecutorPool`
- `src/lumora_probe/bootstrap.py:98-178`
- all `asyncio.to_thread` call sites in capture/storage/decode/report paths

**Root cause:** `executor_workers` is validated and documented, and `ExecutorPool` exists, but
bootstrap does not install or inject it. `asyncio.to_thread` uses the loop default executor.

**Impact:** Operator sizing is ignored. Concurrent decode, SQLite, report, hash, and filesystem work
can contend unpredictably and starve capture persistence.

**Required remediation:** Choose one explicit execution policy. Either install a sized default
executor before any `to_thread` call or inject dedicated bounded executors by workload. Register
shutdown with lifecycle. Measure capture latency under concurrent decode/report load.

### COR-001 — Capture stop admission and queue drain contracts are fragile

**Severity:** Medium / P2  
**Categories:** correctness, maintainability, lifecycle  
**Files:**

- `src/lumora_probe/captures/service.py:437-475,488-556`
- `src/lumora_probe/core/bus.py:70-123`

**Root cause:** `stop_accepting` sets `_accepting=False`, but `start_session` does not check it.
`drain` reaches into private `EventSubscription._queue`. Session finalization performs multiple
publish/drain transitions while the session remains mutable and externally reachable.

**Impact:** New work can enter during shutdown, lifecycle code depends on a private queue shape, and
concurrent stop/interruption can produce invalid transitions or writer races.

**Required remediation:** Enforce admission state in every capture-start/promotion entry point, add
a public subscription `join()`/drain method, serialize per-session transitions, and make repeated
stop/interrupt behavior explicit and tested.

### COR-002 — Missing association state creates unstable correlation IDs

**Severity:** Medium / P2  
**Categories:** correctness, observability, fragile code  
**Files:** `src/lumora_probe/associations/network.py:697-713`

**Trigger:** A callback arrives without stored state, arrives after `_forget`, or callback ordering
differs across pynetdicom versions/error paths.

**Root cause:** `_state_for` creates a fresh `_AssociationState` but does not store it. Repeated
fallback calls for the same association can receive different IDs.

**Impact:** One association may fragment across correlation IDs, breaking the product's core
observability claim and sequence grouping.

**Required remediation:** Establish state exactly once per association identity or emit a stable,
explicit orphan-callback diagnostic. Add rejected, aborted, malformed, and callback-order tests.

### RES-001 — Capture archive extraction has no resource limits

**Severity:** Medium / P2  
**Categories:** security hardening, resource management, availability  
**Files:**

- `src/lumora_probe/captures/format.py:457-479`
- `src/lumora_probe/captures/repository.py:344-386`

**Trigger:** A `.lpcap` from another party contains very many members, a high compression ratio, or
huge declared/uncompressed data.

**Root cause:** Extraction correctly rejects traversal and symlinks but imposes no member count,
per-member size, total expanded size, compression ratio, or free-space policy. Discovery can
materialize archives automatically during rebuild.

**Impact:** Disk exhaustion, long startup/readiness outage, or denial of service. Partial extraction
can remain after failure.

**Required remediation:** Add versioned archive limits, preflight central-directory validation,
streamed byte accounting, temporary extraction, cleanup, and atomic publication. Return structured
errors that identify the rejected archive without exposing unrelated filesystem paths.

### PERF-001 — Repository/API pagination materializes and stats full datasets

**Severity:** Medium / P2  
**Categories:** performance, scalability, API design  
**Files:**

- `src/lumora_probe/captures/repository.py:152-186`
- `src/lumora_probe/web/resources.py:32-38`
- `src/lumora_probe/web/pagination.py:65-74`

**Root cause:** `list_captures` reads all captures and instances and calls filesystem `stat` for
object sizes. Web stores return complete tuples; pagination slices after full materialization.

**Impact:** Request latency and memory scale with the entire repository, not page size. Slow or
remote additional capture roots amplify latency.

**Required remediation:** Add query-level pagination/count contracts, persist derivable object size
in the rebuildable index, avoid per-request filesystem stats, and benchmark at the ratified volume
budgets. Preserve deterministic sort keys.

### PERF-002 — Index rebuild repeatedly recomputes all study projections

**Severity:** Medium / P2  
**Categories:** performance, write amplification  
**Files:** `src/lumora_probe/captures/repository.py:215-227,263-312`

**Root cause:** Every indexed capture calls `rebuild_study_projection`, which deletes and recomputes
all studies/series. A full rebuild repeats this for every capture.

**Impact:** O(n²)-style SQL work and prolonged startup readiness for large repositories.

**Required remediation:** Index all capture/instance/event rows in bounded transactions, then
rebuild studies/series once. Add crash/failure semantics so a partial rebuild is never advertised
ready.

### PERF-003 — Ring-buffer expiry rewrites the entire persisted buffer

**Severity:** Medium / P2 for sustained capture; Low / P3 for short sessions  
**Categories:** performance, disk endurance, scalability  
**Files:** `src/lumora_probe/captures/service.py:130-390`

**Root cause:** Steady-state expiry rewrites all retained records; raw bytes are represented in
JSON/base64. The configured cap can be gigabytes.

**Impact:** Large continuous write amplification, latency spikes, and disk wear under sustained
DICOM traffic.

**Required remediation:** Measure first. If budget fails, use bounded segments/chunks with atomic
metadata rather than one full rewrite. Preserve recovery, ordering, and evidence-integrity tests.
Do not optimize before the production composition path exists and is benchmarked.

### ARC-001 — Persistence stack silently deviates from SQLAlchemy Core decision

**Severity:** Medium / P2 governance; not an immediate correctness defect  
**Categories:** architectural drift, dependency correctness  
**Files:**

- `src/lumora_probe/core/storage.py`
- `pyproject.toml:16-28`
- `docs/architecture-baseline/04-technology-stack.md:204-208`
- `docs/adr/ADR-0006-domain-and-boundary-models.md:17-18,54-56`

**Root cause:** The implementation uses stdlib `sqlite3`; SQLAlchemy is not a runtime dependency.
Accepted architecture names SQLAlchemy Core and assumes Core rows/mappers. No ADR records a
replacement.

**Impact:** Governance drift and misleading contributor guidance. A forced rewrite now would add
risk without demonstrated product value.

**Required remediation:** Do **not** add an unused dependency or rewrite persistence mechanically.
Write an ADR before production remediation concludes: either ratify direct `sqlite3` as the simpler
implementation and update baseline/tooling language, or justify/migrate to SQLAlchemy Core with
measured benefit and full migration tests.

### API-001 — Optional provider defaults hide assembly failures

**Severity:** Medium / P2  
**Categories:** API design, testability, maintainability  
**Files:**

- `src/lumora_probe/web/api.py:178-333`
- `src/lumora_probe/web/health_routes.py:17-31`
- route modules using `InMemoryResourceStore`, `InMemoryOperationRegistry`, or `None`

**Root cause:** The same factory serves tests and production, with optional dependencies defaulting
to healthy/empty behavior. Module-level `app = create_app()` also exposes a hollow application to
`uvicorn lumora_probe.web.api:app`.

**Impact:** Missing production dependencies fail open as empty resources rather than startup
errors. OpenAPI advertises routes that may be permanently unconfigured.

**Required remediation:** Keep a convenient test factory, but add a fail-fast production assembly
validator or separate explicit `create_test_app`. The production app must list required capability
providers and refuse startup if any are missing. Document the CLI as the only production entry or
make the module-level ASGI app production-safe.

### MAINT-001 — Service and adapter ownership is unclear

**Severity:** Low / P3  
**Categories:** cohesion, coupling, maintainability friction, dead scaffolding  
**Files:**

- `src/lumora_probe/associations/service.py` — empty stub
- `src/lumora_probe/settings/repository.py` — empty stub
- web-owned provider protocols across route modules
- `docs/other/lifecycle-manager-wiring-plan.md` — stale assumptions

**Root cause:** Phase scaffolding created conventional files, while implementation accumulated in
network/runtime/web modules. Production adapters were never completed, so bootstrap would need to
understand many concrete classes and web-specific shapes.

**Impact:** A less careful implementation can violate package boundaries, wire test doubles, or
create a large composition root with duplicated mapping logic.

**Required remediation:** Keep adapters at the composition/web edge and use public slice contracts.
Delete truly empty scaffolding only if package conventions permit; otherwise document it as an
intentional boundary placeholder. Supersede stale plans after implementation.

### MAINT-002 — Type and compatibility debt is concentrated outside checked slices

**Severity:** Low / P3  
**Categories:** maintainability, dependency evolution  
**Files:**

- `pyproject.toml:93-97`
- `src/lumora_probe/captures/service.py:725`
- pydicom dataset construction in tests/lite tools

**Root cause:** Strict BasedPyright covers only `core` and `shared`. Current tests emit pydicom
warnings for deprecated `write_like_original`, `is_little_endian`, and `is_implicit_VR` APIs.
FastAPI TestClient also warns about an upcoming HTTPX adapter change.

**Impact:** Application/bootstrap wiring errors and future dependency-major incompatibilities can
remain invisible until upgrade.

**Required remediation:** Expand type checking incrementally after composition stabilizes. Remove
pydicom deprecations while still on v3, add a v4 compatibility test lane before widening the pin,
and address the FastAPI/Starlette test-client migration separately.

## 5. Intentional constraints — do not “fix” these

1. **No authentication/RBAC in v1.** ADR-0009 accepts trusted local/reverse-proxy deployment.
2. **Plugins are trusted in-process code.** ADR-0021 rejects fake sandboxing. Installation remains
   CLI/filesystem-only; do not add an install API.
3. **Loopback by default.** Preserve ADR-0010's explicit non-loopback acknowledgment.
4. **Single process.** Do not add Redis, Kafka, RabbitMQ, Celery, or multi-process workers.
5. **Capture directories are authoritative.** `index.db` remains rebuildable; `app.db` remains
   authoritative for jobs/audit/bookmarks.
6. **Event ordering uses sequence.** Never order by wall-clock `occurred_at`.
7. **Client-asserted viewer events remain quarantined from analysis.**
8. **Wire/byte-exact replay, pcap import, remote collectors, auth, Prometheus exposition, and
   PS3.15 de-identification remain deferred pending ADRs.**
9. **Interop fixtures remain synthetic.** Never introduce patient or de-identified clinical data.
10. **Do not add dependencies merely because the historical baseline lists them.** Resolve drift by
    ADR and demonstrated need.

## 6. Implementation sequence

Work in order. Do not parallelize phases that share bootstrap, lifecycle, capture ownership, or
storage startup. Every phase ends with its acceptance gate before the next begins.

### Phase 0 — Pin scope and decisions

**Goal:** Prevent a fix from silently changing architecture or colliding with concurrent work.

1. Confirm clean worktree or isolate an implementation branch/worktree.
2. Re-read `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, ADR indexes, and this plan.
3. Revalidate PR-001 through PR-004 against current HEAD using `git show`, including the partial
   engine/lifecycle wiring added in `447f635`/`25351b4`.
4. Record one short architecture note defining the required `lumora serve` capabilities:
   event bus, recovered index, ring/capture engine, DICOM listener, projections/API, settings,
   operations, and health.
5. Decide ARC-001 through an ADR before changing persistence technology. Recommended default:
   ratify current `sqlite3` unless SQLAlchemy Core provides a measured required capability.
6. Decide CON-001's off-bus thread ownership. A new ADR is required if the design changes the
   accepted one-thread-boundary or persistence-backpressure model.
7. Treat `docs/other/lifecycle-manager-wiring-plan.md` as complete only for its narrow shutdown
   scope. Reuse its passing adapter criteria, do not repeat that work, and do not mistake it for
   full production composition.

**Exit criteria:** Decisions reviewed; no deferred feature pulled into scope; current HEAD and
worktree state recorded in the implementation PR.

### Phase 1 — Add failing process-boundary acceptance tests

**Goal:** Prove the defect before composing components.

Add a dedicated production smoke test module, preferably `tests/test_production_composition.py`.
Use free TCP ports for HTTP and DICOM; do not hard-code `11112` in parallel tests.

Required tests:

1. Launch `uv run lumora serve` as a subprocess with an isolated data root.
2. Assert readiness is initially false/unavailable until index recovery and services start.
3. Assert final readiness names at least: event bus, app DB, index DB/recovery, capture engine, and
   DICOM listener.
4. Assert the DICOM TCP port is open.
5. Send C-ECHO through `DICOMSCUClient`; assert success and association events.
6. Send one synthetic C-STORE; assert success only after object/ring persistence completes.
7. Promote or create the supported capture form; assert it appears in `/api/v1/captures` and its
   study/instance appears through production projection endpoints.
8. Stop via SIGTERM during active traffic; assert no silently running manifest remains. It must be
   completed or explicitly interrupted.
9. Restart with the same data root; assert prior captures are rebuilt and visible.
10. Assert `/api/v1/settings` returns real default/source entries; update a live setting, restart,
    and assert persistence.
11. Launch with acknowledged non-loopback/container-equivalent host policy; assert configured Host
    succeeds and an unlisted Host fails.
12. Build/install the wheel in an isolated environment and run the same minimal HTTP+DICOM smoke,
    proving package assets and all common packages ship.

These tests must fail on the current implementation for the expected reasons, then pass only after
composition is real.

### Phase 2 — Separate startup storage recovery from service startup

**Goal:** Restore authoritative capture visibility before accepting traffic.

Target files:

- `src/lumora_probe/bootstrap.py`
- `src/lumora_probe/core/storage.py` only if a clearer app/index initialization API is needed
- `src/lumora_probe/captures/repository.py`
- production composition tests

Steps:

1. Initialize directories and version marker.
2. Migrate `app.db` idempotently without touching `index.db` twice.
3. Construct `CaptureRepository` with the production clock.
4. Rebuild/recover index from primary and additional roots before readiness.
5. Quarantine/report malformed packages with structured diagnostics; define whether one bad package
   blocks all readiness. Prefer preserving good evidence while clearly reporting degraded state.
6. Recompute study/series projections once per rebuild, not once per capture.
7. Persist object sizes in the rebuildable index if required for paginated reads.
8. Sweep running durable jobs to interrupted as ADR-0023 requires.

**Acceptance criteria:** Two-restart test preserves capture visibility; torn active package becomes
interrupted; no blank-index ready window; corrupt archive behavior is explicit and tested.

### Phase 3 — Build one production service graph and lifecycle

**Goal:** Make bootstrap the sole composition root without violating slice imports.

Construct, in dependency order:

1. Clock and ID generator.
2. Data paths and recovered storage/repositories.
3. Sized executor policy.
4. Event bus.
5. Runtime settings store and initial settings snapshot.
6. Reuse/complete the newly composed ring buffer, capture repository, capture engine, and lifecycle
   adapter; add startup rebuild and health rather than constructing duplicates.
7. DICOM listener/relay configuration with thread-safe event and fidelity ingress.
8. Study/instance projection, object source, decode/frame, and metadata services.
9. Durable operation registry/job registry.
10. Replay runtime with explicit target/allowlist policy; do not invent an unsafe write route.
11. Report evidence/service/job provider.
12. Bookmark, audit, metrics, alerts, plugins, transfer inspector, and search/log providers.
13. Web adapters over public contracts.

Lifecycle requirements:

- Event bus starts before any thread can call `publish_from_thread`.
- Capture ingress/engine starts before DICOM listener accepts associations.
- Listener is the first component to stop accepting.
- Accepted ingress drains before writers flush/fsync/seal.
- Deadline expiry interrupts active captures with an explicit reason.
- Executor closes only after all services using it stop.
- Bus/live hub close after persistence subscribers drain.
- Startup failure unwinds only already-started resources in reverse order.
- Every service contributes health; lifecycle state is exposed on `application.state` for tests.

Use thin adapters only where method signatures differ. Keep cross-slice concrete imports in
`bootstrap.py`; application slices may consume only other slices' `contracts.py`.

**Acceptance criteria:** PR-001 and PR-003 process tests pass; no private attribute access is needed
for drain; startup failure leaves both ports closed and resources released.

### Phase 4 — Replace empty production web providers

**Goal:** Make every advertised live route read/write the production domain.

1. Introduce explicit production adapters for captures, associations, events, studies/projections,
   operations, settings, frames, metadata, reports, bookmarks, and workspace data.
2. Do not preload all records into `InMemoryResourceStore` at startup; adapters must query their
   repositories with pagination/filter contracts.
3. Do not wire `FilesystemCaptureStore` directly for deletion. Its `rmtree` trusts a record path
   and lacks primary/additional-root policy. Route deletion through the accepted capture-deletion
   cascade service with containment, audit, bookmark cascade, and read-only-root refusal.
4. Add a production dependency validator. Missing required providers must abort startup with a
   structured error, not return empty collections.
5. Decide module-level `web.api:app` behavior: either remove it as a supported production entry,
   make it fail clearly, or make it call the real composition through an environment-aware factory.
6. Regenerate `docs/generated/openapi-v1.json` only if the HTTP contract changes.

**Acceptance criteria:** Seeded persisted data is visible through every relevant route after restart;
no production route instance contains `InMemory*`/`Null*` provider classes; missing provider test
fails startup.

### Phase 5 — Make settings real and live

**Goal:** Satisfy ADR-0020 end to end.

1. Adapt `RuntimeSettingsStore.snapshots()` to the web `items` contract.
2. Load operator file/env values and report `default|file|env|runtime` provenance.
3. Persist runtime values to `DataPaths.settings` atomically.
4. Inject event bus, clock, and IDs so `ConfigurationChanged` is observed and captured.
5. Define per-setting appliers:
   - ring-buffer duration/bytes/events-only;
   - decode cache budget;
   - AE/IP allowlists;
   - read-only policy;
   - rule toggles;
   - theme/live UI settings.
6. Make locked and restart-required values fail with existing structured errors.
7. Audit old/new values with sensitive-name redaction. Do not audit only key names if operational
   provenance requires the effective non-sensitive values.
8. Ensure live apply and persistence are consistent. Define rollback if one succeeds and the other
   fails.

**Acceptance criteria:** Update changes behavior immediately, survives restart, emits one observed
configuration event, preserves source locks, and does not report success on apply failure.

### Phase 6 — Repair network and plugin trust boundaries

**Goal:** Keep accepted unauthenticated deployment usable without weakening safeguards.

Network tasks:

1. Add startup config fields and source tracking for allowed hosts/origins/trusted proxies.
2. Normalize IPv4, bracketed IPv6, hostnames, and ports consistently for HTTP and WebSocket.
3. Preserve Host, Origin, `Sec-Fetch-Site`, CORS removal, and read-only checks.
4. Treat forwarded headers as trusted only when the socket peer is configured.
5. Update Docker and reverse-proxy docs with explicit allowlists.
6. Test DNS-rebinding Host, hostile Origin, forged forwarded headers, IPv6 loopback, configured LAN
   hostname, and WebSocket parity.

Plugin tasks:

1. Validate plugin ID grammar in the domain manifest before path construction.
2. Assert resolved destination is a direct contained child before copying.
3. Reject/canonicalize platform-specific separators and Windows drive/device names.
4. Copy to a temporary child; validate manifest/entry point/symlink policy; atomically publish.
5. Clean all partial copies on failure.
6. Make invalid discovered plugins visible as diagnostics rather than silently skipping every parse
   failure, without loading their code.

**Acceptance criteria:** SEC-001/SEC-002 tests pass on Linux, macOS, and Windows CI. Unknown Host and
Origin remain denied. Malicious plugin IDs create no file outside the plugin root.

### Phase 7 — Resolve capture concurrency and backpressure

**Goal:** Make capture integrity true under real pynetdicom concurrency.

1. Implement the ratified CON-001 ownership mechanism.
2. Ensure session map and each writer have one transition owner.
3. Bound pending DICOM-to-loop/capture submissions, not only the final queue.
4. Observe every thread-publish future; convert failure/timeout to a metric, diagnostic, and
   appropriate DICOM status.
5. Enforce `_accepting` in session creation/promotion and prevent work after shutdown begins.
6. Add a public subscription drain API and remove `_queue` access.
7. Make C-STORE parse/write status semantics explicit. Distinguish malformed dataset, out-of-space,
   temporary resource failure, and internal failure where DICOM status allows it.
8. Stabilize orphan callback association correlation.

Adversarial tests:

- multiple simultaneous associations and C-STOREs;
- stop session while C-STORE/object write is in flight;
- SIGTERM while ingress and capture queue are saturated;
- event-loop stall and queue saturation;
- disk full/write failure;
- callback after release/abort;
- shutdown deadline expiry;
- repeated stop/interrupt calls.

**Acceptance criteria:** No silent drop on capture path, bounded memory, deterministic manifests,
gap-free sequence per capture, and all failures observable.

### Phase 8 — Add archive/resource limits and performance work

**Goal:** Meet volume budgets without changing evidence semantics.

1. Define `.lpcap` limits from accepted volume budgets: member count, per-file bytes, total expanded
   bytes, compression ratio, path length, and extraction deadline/free-space margin.
2. Preflight and stream-account extraction into a temporary directory; clean on failure.
3. Add repository-level page/count/filter queries and stable indexes.
4. Store object size in rebuildable projections; remove per-request `stat` loops.
5. Rebuild study/series once per index rebuild.
6. Benchmark ring-buffer steady-state expiry. Introduce segmented persistence only if current design
   misses the budget.
7. Review JSONL file-open/fsync cost under production fidelity. Preserve `FsyncPolicy.ALWAYS` where
   evidence durability requires it; optimize handle lifecycle, not durability semantics.
8. Add metrics for queue depth, pending thread submissions, index rebuild progress/duration,
   archive rejection, executor saturation, and ring rewrite bytes.

**Acceptance criteria:** Benchmarks at ratified capture/object volume stay within documented latency,
memory, startup, and disk-write budgets. Resource-limit failures are structured and leave no partial
published capture.

### Phase 9 — Dependency, package, provider, and CI closure

**Goal:** Make release evidence match the shipping artifact.

1. Resolve ARC-001 ADR and align `CLAUDE.md`, baseline, and `pyproject.toml`.
2. Run `uv lock` only if dependency metadata changes; use `uv sync --locked` thereafter.
3. Remove pydicom v4 deprecations and add compatibility tests before changing `<4.0`.
4. Verify `lumora_dicom_common` and all assets/templates ship in wheel and sdist.
5. Install wheel and sdist independently on Linux, macOS, and Windows; run CLI imports and minimal
   production smoke.
6. Keep `lumora serve` HTTP+DICOM composition in release gates; the source-checkout process smoke is now present, with installed-artifact smoke still pending.
7. Keep full external interop scheduled if too expensive for PRs, and make a failed scheduled run
   visible/blocking for release promotion rather than ignorable evidence.
8. Rerun dependency audit from exported locked requirements in CI. Save the report artifact/SBOM.
9. Expand BasedPyright in manageable slices: bootstrap/web adapters first, then captures,
   associations, studies, replay, reports, plugins, settings.
10. Regenerate OpenAPI/event/condition catalogs and frontend assets only when their sources change.

**Acceptance criteria:** Clean wheel/sdist install, no missing package/assets, current vulnerability
report, no unreviewed warnings at startup, and production smoke against installed artifacts.

### Phase 10 — Documentation and release correction

**Goal:** Ensure claims equal verified behavior.

1. Until remediation ships, update release status/known limitations so GA does not claim a working
   production listener/composition that is absent.
2. After remediation, update README quick start with verified listener, host allowlist, proxy, and
   settings behavior.
3. Update troubleshooting health service list and index-rebuild diagnostics.
4. Document archive limits, disk sizing, backup/restore, and interrupted capture behavior.
5. Record the final architecture decision(s) and supersede stale implementation plans without
   rewriting accepted ADR history.
6. Update Phase 20 acceptance matrix to point to production process tests, not only isolated
   component tests.
7. Add a release note for any API behavior change from silent empty provider to startup failure.

## 7. Test and acceptance matrix

| Requirement | Required evidence |
|---|---|
| Production starts advertised services | Subprocess test checks HTTP and DICOM ports plus named readiness services. |
| DICOM capture works end to end | Synthetic C-ECHO/C-STORE through `lumora serve`; capture/object/event visible through API. |
| Restart recovery works | Same data root after restart; active capture interrupted; sealed capture remains visible. |
| Graceful shutdown preserves evidence | Saturated ingress + SIGTERM; drain/flush/seal or explicit interruption. |
| Readiness is honest | Each required service forced down separately; readiness 503 names failing service. |
| Runtime settings are real | Live behavior change, provenance, lock refusal, persistence after restart. |
| Network gate is safe and usable | Loopback default, unacknowledged bind refusal, configured host success, hostile Host/Origin failure. |
| Plugin installer is contained | Unix/Windows traversal IDs, symlinks, partial-copy failure, atomic successful install. |
| Capture concurrency is safe | Parallel association/store/stop stress with deterministic manifests and no silent drops. |
| Archive extraction is bounded | Zip-slip, symlink, duplicate, high ratio, member count, total size, cleanup tests. |
| API scales by page | Query count/rows bounded by page; stable pagination under inserts; no full object `stat` scan. |
| Package is complete | Wheel/sdist install and production smoke on three supported OS families. |
| Cross-provider support is real | DCMTK, dcm4che, Orthanc exercise shipping composition where feasible. |
| Dependency security is current | Exported-lock `pip-audit --strict` passes; result retained. |
| Architecture remains enforced | Ruff, import-linter, expanded BasedPyright, generated-artifact checks pass. |

## 8. Rollout, observability, and rollback

### Rollout

1. Ship remediation as a new patch/minor release; do not silently replace the signed-off `0.1.0`
   behavior without release notes.
2. Test against a copied production-like data root containing sealed, interrupted, corrupt, and
   dropped `.lpcap` captures.
3. Back up `app.db`, captures, ring buffer, settings, and version marker before first upgraded start.
4. Start in loopback/read-only mode first. Wait for index rebuild and readiness.
5. Compare capture/study/instance counts and sample manifest digests before enabling DICOM ingress.
6. Enable DICOM listener on a synthetic source; verify C-ECHO/C-STORE and API visibility.
7. Enable reverse proxy/non-loopback only after Host/Origin/proxy configuration is explicit.
8. Monitor at least one full retention window before broadening use.

### Required observability

- lifecycle state and startup/unwind failures;
- index rebuild discovered/indexed/quarantined counts and duration;
- DICOM listener bind and active associations;
- event ingress depth, pending thread submissions, publish failures/timeouts;
- capture queue depth, active sessions, fsync/write failures, interrupted captures;
- executor active/queued work by workload;
- ring-buffer bytes/records/rewrite bytes/evictions;
- settings apply and persistence failures;
- archive rejection reason and expanded-byte count;
- plugin discovery/install/enable failures;
- readiness reason per required service.

Do not log DICOM object bytes, patient attributes, credentials, secrets, or unrestricted filesystem
paths. Preserve correlation IDs and capture/association IDs needed for engineering diagnosis.

### Rollback

1. Stop accepting DICOM and allow bounded drain.
2. Back up any captures created by the new release.
3. Roll back application version while preserving capture directories and `app.db`.
4. Delete/rebuild only `index.db`; never delete `app.db` or capture evidence as rollback cleanup.
5. Restore prior `settings.toml` if schema changed; settings migration must be backward-aware or
   versioned.
6. Re-run readiness and capture-count reconciliation before reopening traffic.

## 9. Completion checklist

Implementation is complete only when all boxes are true:

- [x] Partial engine/lifecycle wiring is retained, completed, and covered at the process boundary.
- [x] PR-001 through PR-004 composition/recovery/settings acceptance passes; residual lanes remain tracked.
- [x] SEC-001 is fixed; SEC-002 startup gates and configured-host process coverage pass without weakening exposure policy.
- [x] CON-001/CON-002 ownership and saturation behavior are ratified and adversarially tested (ADR-0036; `tests/test_production_concurrency.py`).
- [x] `executor_workers` controls the production default executor.
- [x] Startup rebuilds/reconciles authoritative captures before readiness.
- [x] No production route uses an empty in-memory/null provider for every advertised optional capability; production-required providers are wired (`tests/test_production_composition.py`).
- [x] Runtime settings persist, report provenance, and supported settings apply live.
- [x] DICOM port and HTTP API are verified through installed wheel and sdist smoke environments.
- [x] Graceful shutdown and deadline interruption preserve explicit evidence state at component and process level (`tests/test_bootstrap.py`, `tests/test_production_composition.py`).
- [x] Archive extraction and plugin installation are contained and bounded.
- [x] Database pagination and rebuild performance meet ratified budgets on the documented local reference host; no network-filesystem claim is made.
- [x] SQLAlchemy/sqlite3 architecture drift is resolved by accepted ADR and documentation.
- [x] Ruff check and format pass.
- [x] Import-linter passes all contracts.
- [x] BasedPyright passes its expanded application slices; core/shared and bootstrap pass (canonical `uv run basedpyright`).
- [x] Full pytest passes; remaining skips are justified/opt-in, and final release-required interoperability ran separately in hosted CI.
- [x] Frontend assets match source (`npm run check:assets`); generated event/OpenAPI artifacts were not changed.
- [x] Exported-lock dependency audit passes; CI retains the report artifact.
- [x] Final-SHA pinned-container DICOM interoperability passes against DCMTK, dcm4che, and Orthanc (`15 passed, 0 failed`; CI run `30716410290`, job `91412594111`).
- [x] README, known limitations, troubleshooting, upgrade, and release status match verified behavior (`docs/release-notes-0.1.0.md`).
- [x] No real or de-identified patient data was introduced; release tests and fixtures use synthetic DICOM UIDs/data only.

### Release-closure evidence update — August 1, 2026

The closure implementation at `05474d5` adds ADR-0036 and ADR-0037, a production runtime verification handle,
bounded DICOM ingress and capture ownership, segmented ring persistence, SQL-backed pagination,
canonical whole-package strict typing, installed wheel/sdist smoke, and adversarial shutdown/traffic
tests. Local evidence is recorded in `docs/planning/phase-18-performance-report.md` and
`docs/release-notes-0.1.0.md`. Hosted CI run `30716410290` passed source quality plus all six
installed-artifact jobs, the dependency-audit step, and final-SHA interoperability. Reference
performance gates pass on the documented local host; universal and network-filesystem performance
claims remain intentionally out of scope.

## 10. Final implementation guidance

Prefer deletion and reuse over new abstractions. The codebase already contains most domain,
repository, networking, replay, report, settings, lifecycle, and operation implementations. The
primary task is to compose them safely and add the missing production adapters/tests—not rewrite
them.

When an existing interface does not fit, first check its slice `contracts.py`. Add the smallest
public contract needed rather than importing another slice's repository or domain internals. Keep
all concrete cross-slice construction in `bootstrap.py` or a narrowly owned composition module.
Never make a failing acceptance test pass by substituting an in-memory provider, suppressing
readiness probes, dropping capture events, weakening Host/Origin checks, or changing documentation
alone.
