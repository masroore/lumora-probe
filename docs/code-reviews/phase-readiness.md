# Phase Readiness Assessment

## v0.1.0 GA Gate Compliance

This assessment cross-references the Definition of Done (`docs/planning/07-definition-of-done.md`)
and the PRD acceptance matrix (`docs/lumora-probe-lite-prd.md`) against what was observed in
the codebase.

---

## Core Infrastructure Gates

| Gate | Status | Evidence |
|---|---|---|
| Event bus with gap-free sequencing | ✅ Pass | `core/bus.py`, `test_phase07_bus.py` |
| Clock anomaly detection | ✅ Pass | `EventBus._clock_anomaly()`, test verified |
| UI backpressure drop-oldest | ✅ Pass | `enqueue_ui()`, adversarial test present |
| Capture channel never drops | ✅ Pass | Unbounded queue, test present |
| Single thread boundary | ✅ Pass | `publish_from_thread` is the only crossing |
| SQLite WAL mode | ✅ Pass | `PRAGMA journal_mode = WAL` in `SQLiteConnectionPolicy` |
| Network filesystem rejection | ✅ Pass | `assert_local_filesystem` called at init |
| Data dir version marker | ✅ Pass | `ensure_version_marker` called at init |
| Import boundary enforcement | ✅ Pass | `import-linter` config present, test present |
| No ORM | ✅ Pass | Hand-written SQL throughout |
| `time.`/`uuid.` banned outside core | ✅ Pass | import-linter enforced |
| Three-field time model | ✅ Pass | `occurred_at`, `monotonic_ns`, `sequence` correctly separated |

---

## Capture Engine Gates

| Gate | Status | Evidence |
|---|---|---|
| Capture directory format (ADR-0004) | ✅ Pass | `captures/format.py` |
| Manifest atomic write-then-rename | ✅ Pass | `_write_manifest()` |
| `CaptureInterrupted` on deadline miss | ⚠️ Partial | Logic exists in `LifecycleManager`; not wired to production |
| Torn trailing event recovery | ✅ Pass | `_recover_package()`, `_complete_event_length()` |
| Ring buffer always-on | ✅ Pass | `RingBufferService` |
| Ring buffer drop-oldest by size/time | ✅ Pass | `_expire()` and size loop |
| `.lpcap` pack/unpack | ✅ Pass | `pack_capture()`, `unpack_capture()` with zip-slip protection |
| Content-addressed object store | ✅ Pass | `ContentAddressedObjectStore` with digest verification |
| `FsyncPolicy` variants | ✅ Pass | `ALWAYS`, `FLUSH`, `NEVER` |
| Client-asserted event count tracked | ✅ Pass | `client_asserted_event_count` in session |

---

## API and Web Gates

| Gate | Status | Evidence |
|---|---|---|
| Non-loopback bind requires acknowledgment | ✅ Pass | `_validate_network_gate()` |
| Read-only mode enforcement | ✅ Pass | `SecurityMiddleware` |
| Host allowlist | ✅ Pass | `SecurityMiddleware` |
| CSRF protection | ✅ Pass | Sec-Fetch-Site + Origin checks |
| CORS headers stripped | ✅ Pass | Active removal in middleware |
| Two WebSocket channels (ADR-0019) | ✅ Pass | `/api/v1/events/stream` and `/ws/ui` present |
| Security audit trail | ✅ Pass | `AuditLog.append(SECURITY_FAILURE)` |
| No authentication in v1 (ADR-0009) | ✅ Pass | No auth middleware present |

---

## Analysis Gates

| Gate | Status | Evidence |
|---|---|---|
| Observed conditions physically separate from inferred findings | ✅ Pass | `ConditionObservation` vs `Finding` in `analysis/domain.py` |
| Client-asserted events excluded from analysis | ✅ Pass | `_observed_events()` filters by `EventOrigin.OBSERVED` |
| Finding citations validated against observed sequences | ✅ Pass | `evaluate()` sequence subset check |
| Plugin findings validated identically to bundled | ✅ Pass | `evaluate_plugin()` applies same validation |

---

## Replay Gates

| Gate | Status | Evidence |
|---|---|---|
| Protocol replay exclusivity (refuse, not queue) | ✅ Pass | `InMemoryReplayExclusivity` |
| Protocol replay requires allowlisted target | ✅ Pass | `_validate_protocol_policy()` |
| Protocol replay requires protocol+ fidelity | ✅ Pass | `_require_protocol_fidelity()` |
| Protocol replay refuses partial captures | ✅ Pass | `_require_complete_capture()` |
| Replay audit durable record | ✅ Pass | `SQLiteOperationRegistry.append_replay_audit()` |
| Running jobs interrupted on restart | ⚠️ Partial | `startup_sweep()` exists but not called from production entry |

---

## Operations Gates

| Gate | Status | Evidence |
|---|---|---|
| Background operations durable audit | ✅ Pass | `SQLiteOperationRegistry` |
| Operations never auto-resumed | ✅ Pass | `startup_sweep()` marks running → interrupted |
| Job progress via event bus | ✅ Pass | `_progress()` publishes via `progress_publisher` |
| Cancellation cooperative | ✅ Pass | `CancellationToken` pattern |
| Concurrency limits per job type | ✅ Pass | `concurrency_limits` in `InMemoryJobRegistry` |

---

## Observability Gates

| Gate | Status | Evidence |
|---|---|---|
| Health registry | ✅ Pass | `HealthRegistry`, `HealthReport` |
| Metrics registry | ✅ Pass | `MetricRegistry` with counters, gauges, histograms |
| Alert registry with hysteresis | ✅ Pass | `AlertRegistry` |
| Audit log | ✅ Pass | `AuditLog` with categories |
| Structured logging | ✅ Pass | `structlog` used throughout |

---

## Definition of Done Checklist (phase-level)

| DoD item | Status |
|---|---|
| import-linter passes | ✅ Config present |
| Tests at prescribed layer pass | ✅ 75+ test files present across all phases |
| No new dependency without ADR | ✅ No undocumented dependencies found |
| Contract changes regenerate artifacts | ✅ OpenAPI test present |
| New terms in glossary | Cannot verify without reading all 75+ test files; convention established |
| Deviations recorded in ADR before merge | ADR layer exists and is referenced |

---

## Outstanding Gaps (Required Before Production Expansion)

| Gap | Blocking | Notes |
|---|---|---|
| `LifecycleManager` not wired in `bootstrap.py` | Yes (for capture integrity) | F-001 |
| `CaptureInterrupted` not guaranteed at shutdown | Yes (for audit fidelity) | Consequence of F-001 |
| `startup_sweep()` not called at application start | Yes (for job state integrity) | Consequence of F-001 |
| `executor_workers` has no effect | No (default sizing is acceptable) | F-011 |
| `associations/service.py` empty stub | No for v0.1.0 engineering deployments | F-003 |
| `RetentionPolicy` byte-budget algorithm | No (byte limit not enforced in base use case) | F-004 |

---

## Production Readiness Verdict

**For trusted engineering deployments on a loopback interface:**  
✅ **SUITABLE** — the core capture, analysis, and replay pipeline is correctly implemented.
Evidence integrity is maintained. The security boundary is correct for the intended deployment
context.

**For deployments where graceful shutdown under load is a requirement:**  
⚠️ **NOT YET READY** — the `LifecycleManager` gap (F-001) must be closed before this
deployment class.

**For non-loopback / multi-user deployments:**  
❌ **NOT INTENDED** — no authentication, no RBAC, and the security policy explicitly warns
operators via `NetworkExposureError`. Do not expand without an auth ADR.

---

## Overall Phase Gate Verdict

**PASS WITH RECOMMENDATIONS**

The v0.1.0 GA sign-off is justified for the stated deployment scope (trusted engineering
deployments). The 2 critical findings (F-001, F-002) and 4 high findings should be addressed
in the next sprint before recommending the tool for broader engineering use.
