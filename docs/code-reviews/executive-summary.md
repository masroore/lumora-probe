# Executive Summary

## Overall Verdict: PASS WITH RECOMMENDATIONS

Lumora Probe v0.1.0 is a well-structured, architecturally coherent codebase that largely honours
the constraints recorded in its 32 ADRs. The design is notably disciplined for a single-engineer
project at this phase. The core event bus, capture engine, storage layer, and security middleware
are well-implemented. Several correctness issues and a small number of architectural concerns
warrant attention before expanding to a wider deployment audience, but none block engineering
deployments as intended for this release.

---

## Overall Engineering Assessment

**Positive signals:**
- Architecture is genuinely slice-first with enforced import boundaries. The ADR layer is
  authoritative and the code follows it with high fidelity.
- The event bus is correctly concurrency-annotated and the one thread boundary (pynetdicom →
  `call_soon_threadsafe`) is explicit and safe.
- Evidence integrity is taken seriously. Observed conditions and inferred findings are physically
  separate. Client-asserted events are quarantined. Byte-faithful persistence is verified.
- The error hierarchy (`LumoraError`, structured context, machine-readable codes) is clean and
  consistently used.
- Value objects are immutable, invariant-checked, and framework-free.
- SQLite usage is correct: WAL mode, single writer lock, `busy_timeout`, foreign keys enforced,
  network-filesystem rejection, separate index/app databases.
- Test strategy follows the prescribed component-over-unit pyramid. Real SQLite and real pydicom
  are used in component tests.

**Concerns requiring action:**
- Several correctness defects in the capture service, storage layer, and metrics registry.
- `bootstrap.py` does not register the `CaptureEngine`, `DICOMListener`, or `ReplayRuntime`
  with the `LifecycleManager`, making graceful shutdown incomplete at the production composition
  level.
- `CaptureEngine.drain()` accesses `self._subscription._queue` directly (private attribute),
  bypassing the public `EventSubscription` API.
- `RetentionPolicy.select()` has an asymmetric byte-budget algorithm that can silently under-retain
  captures.
- The `associations/service.py` is an empty stub — the DICOM listener wiring is absent from the
  composition root.
- `_counter()` in `MetricRegistry` overloads argument parsing with a special-cased `amount` label
  which leaks implementation detail.

---

## Architecture Compliance Summary

| Concern | Status | Notes |
|---|---|---|
| Slice layout (core/shared/captures/…) | ✅ Compliant | All expected packages present |
| Import-linter boundary contract | ✅ Compliant | No cross-slice repository access found |
| No ORM (ADR-0006, `04` §6) | ✅ Compliant | Hand-written row↔domain mapping throughout |
| Single thread boundary | ✅ Compliant | `publish_from_thread` is the only crossing |
| Clock/ID injection (ADR-0022) | ✅ Compliant | `time.` / `uuid.` not used outside `core/` |
| Backpressure split by channel | ✅ Compliant | `CAPTURE` never drops, `UI` drops-oldest |
| DICOM port 11112, not 104 | ✅ Compliant | Default in `DICOMListenerConfig` |
| No auth in v1 (ADR-0009) | ✅ Compliant | `SecurityPolicy` enforces host/origin, not identity |
| Two WebSocket sockets (ADR-0019) | ✅ Compliant | `/api/v1/events/stream` and `/ws/ui` distinct |
| Data dir version marker | ✅ Compliant | `ensure_version_marker` present |
| Rebuildable index (ADR-0023) | ✅ Compliant | `index.db` drop-and-rebuild confirmed |
| Production composition root wires services | ⚠️ Partial | `LifecycleManager` not used in `bootstrap.py` |
| `associations/service.py` stub | ⚠️ Incomplete | File is a one-liner `__all__` stub |

---

## Implementation Completeness

Core infrastructure (bus, clock, IDs, storage, paths, config, errors, lifecycle): **Complete**  
Captures slice (domain, service, format, repository, handover): **Complete**  
Associations domain: **Complete** (network.py is substantial)  
Associations service: **Stub only**  
Analysis slice: **Complete**  
Replay slice: **Complete**  
Reports slice: **Complete**  
Plugins slice: **Complete**  
Settings slice: **Complete**  
Web layer: **Substantially complete** (14+ route files)  
Bootstrap / composition root: **Partial** (services not lifecycle-managed)  

---

## Major Strengths

1. The event envelope contract with registry, payload catalog, and byte-faithful persistence is
   an excellent engineering foundation. Unknown fields are preserved, not stripped.
2. `EventBus` implements the exact backpressure split and clock-anomaly detection specified in
   the architecture documents.
3. `ContentAddressedObjectStore` uses atomic write-then-rename with fsync; no partial objects
   can appear.
4. The `assert_contained` / `resolve_capture_path` path-traversal guard is correct and used
   consistently at the HTTP and storage boundary.
5. `SecurityMiddleware` implements Sec-Fetch-Site checking plus host allowlist in a single
   composable seam. CORS headers are actively stripped from responses.
6. Error hierarchy is disciplined: structured codes, operator-facing message, actionable
   remediation, machine-readable context on every error.
7. UUIDv7 generator implementation is correct and the seeded test double is clean.
8. `LifecycleManager` implements ordered startup, reverse shutdown, and bounded grace period
   with proper `CaptureInterrupted` semantics.

---

## Critical Findings

1. **`bootstrap.py` does not register services with `LifecycleManager`** — graceful shutdown
   and the bounded drain-before-close guarantee are not exercised in production.  
   (See findings.md F-001)

2. **`CaptureEngine.drain()` accesses `_queue` via private attribute** — bypasses the
   `EventSubscription` public contract and will break if the queue structure changes.  
   (See findings.md F-002)

---

## High Priority Findings

3. **`associations/service.py` is an empty stub** — the composition root has no path to wire
   the DICOM listener into captures or associations.  
   (See findings.md F-003)

4. **`RetentionPolicy.select()` byte-budget loop silently skips captures** — any capture whose
   individual size exceeds remaining budget is silently excluded even when it would fit if
   a smaller capture before it were dropped.  
   (See findings.md F-004)

5. **`_counter()` special-cases `amount` key inside generic label code** — the `events.dropped`
   counter is the only one that passes `amount` and the special case mutates `labels` mid-call.  
   (See findings.md F-005)

6. **`CaptureEngine.stop_session()` calls `drain()` twice between lifecycle transitions** —
   both `CaptureStopped` and `CaptureCompleted` drain the ingress queue, making the sequence
   depend on event ordering across re-entrant awaits.  
   (See findings.md F-006)

---

## Technical Debt Summary

- 8 modules are one-liner stubs (`__all__: tuple[str, ...] = ()`), of which
  `associations/service.py` is the most consequential gap.
- 9 topics deferred by ADR (pcap import, byte-exact replay, remote collectors, auth/RBAC,
  plugin API install, config profiles, DIMSE-N, Prometheus, PS3.15 de-identification) are
  correctly not implemented and not pretended to exist.
- `bootstrap.py` does not integrate `LifecycleManager`; the production entrypoint lacks the
  graceful-shutdown guarantee that the architecture documents and lifecycle tests rely on.

---

## Production Readiness Assessment

**Suitable for:** trusted engineering deployments on a loopback interface with manual oversight.  
**Not suitable for:** production deployments where graceful shutdown under load must be guaranteed,
multi-user access, or any deployment where replay-on-restart guarantees matter.

The bounded-drain shutdown and interrupt-on-deadline logic exist and are tested in isolation but
are not exercised at the production entry point. This gap should be closed before recommending
the tool to users who care about capture integrity across process restarts.

---

## Recommended Next Actions (priority order)

1. Wire `LifecycleManager` in `bootstrap.py` and register `EventBus`, `CaptureEngine`,
   `DICOMListener`, `ReplayRuntime` as services.
2. Replace `CaptureEngine.drain()`'s private `_queue` access with `EventSubscription.get()`
   or expose `EventSubscription.queue_empty()`.
3. Implement `associations/service.py` or document the gap as a known limitation.
4. Fix `RetentionPolicy.select()` byte-budget algorithm to include captures in order of size
   rather than silently skipping.
5. Refactor `MetricRegistry._counter()` to remove the `amount` special-case; use a separate
   `increment_by(name, n)` method.
6. Add adversarial test for graceful shutdown under active capture.
