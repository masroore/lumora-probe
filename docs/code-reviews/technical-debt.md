# Technical Debt

## 1. Explicit Stub Modules

Eight modules are one-liner stubs (`__all__: tuple[str, ...] = ()`):

| Module | Impact | Notes |
|---|---|---|
| `associations/service.py` | **High** | DICOM listener wiring is absent from the composition root. No path exists to start the listener, subscribe it to captures, or expose its health. |
| `core/domain.py` | Low | No domain objects belong in core; stub is appropriate. |
| `core/contracts.py` | Low | No cross-core contracts yet; stub is appropriate. |
| `core/repository.py` | Low | No core repository yet; stub is appropriate. |
| `core/service.py` | Low | No core service yet; stub is appropriate. |
| `shared/domain.py` | Low | Shared domain types live in `shared/value_objects.py`. The stub is appropriate. |
| `shared/contracts.py` | Low | Stub appropriate. |
| `captures/repository.py`'s `__all__` | Low | `CaptureRepository` exists but `__all__` is empty. |

`associations/service.py` is the only consequential stub. The listener, SCU client, and
association pair management live in `associations/network.py`, but there is no service layer
that composes them with the bus, the capture engine, or the repository. In production, the
listener is created directly in `bootstrap.py` — without the association service layer, there
is no way to manage allowlists, expose association history, or register association-level health.

---

## 2. Deferred ADR Topics (Correctly Not Implemented)

Per CLAUDE.md, the following nine topics are deferred pending their own ADR. They are listed
here for completeness to confirm they are correctly absent:

1. **pcap import** — no pcap parsing code found. ✅ Correctly absent.
2. **byte-exact replay** — `ProtocolReplayService` replays at original timing but does not
   guarantee byte-exact PDU reconstruction. ✅ Correctly absent.
3. **remote collectors** — no remote collection code. ✅ Correctly absent.
4. **auth/RBAC** — `SecurityPolicy` enforces host/origin only. ✅ Correctly absent.
5. **plugin install over API** — no `/api/v1/plugins/install` endpoint. ✅ Correctly absent.
6. **config profiles** — single configuration set. ✅ Correctly absent.
7. **DIMSE-N enrichment** — no N-EVENT-REPORT, N-GET, etc. ✅ Correctly absent.
8. **Prometheus exposition** — `MetricRegistry` exposes internal JSON only. ✅ Correctly absent.
9. **PS3.15 de-identification** — redaction is explicitly partial. ✅ Correctly absent.

---

## 3. Lifecycle Manager Not Wired (Critical Technical Debt)

`LifecycleManager` exists in `core/lifecycle.py`, is tested in isolation, and is a well-designed
service orchestration primitive. It is not used in `bootstrap.py`. This is the largest single
piece of outstanding technical debt.

Consequence: Every clean shutdown relies on the ASGI server's implicit cleanup, which does not
guarantee:
- Event bus drain
- Capture engine flush
- `CaptureInterrupted` being written for in-progress captures
- Job registry startup sweep (interrupt-running-jobs) on next start

The only mitigation is that `DICOMListener.drain()` is an async no-op (it waits 100ms for each
active association), and the ring buffer periodically persists. A hard kill will leave active
capture sessions without `CaptureInterrupted` markers.

---

## 4. `executor_workers` Configuration Has No Effect

`StartupConfig.executor_workers` is defined, documented, and validated (1–256). However,
`asyncio.to_thread()` uses Python's global default executor, which is sized by Python's own
heuristic (min(32, cpu_count + 4)). The `ExecutorPool` in `core/lifecycle.py` exists but is
not wired into `bootstrap.py` nor set as the loop's default executor.

**Impact:** On a 2-CPU machine, the default executor has 6 threads; on a 32-CPU machine it has
32. The `executor_workers` setting gives operators no actual control.

---

## 5. `is_uuid7()` Location

`is_uuid7()` is defined in `core/config.py` and imported by `captures/format.py`,
`shared/events.py`, and `core/paths.py`. It belongs in `core/ids.py` alongside the UUID
generation code. Its current location creates an unnecessary import coupling between capture
format code and the configuration module.

---

## 6. `indexed_at` Semantics Bug

`CaptureRepository._record_from_package()` sets `indexed_at=manifest.created_at`. This means
the "when was this indexed" field always equals "when was this captured". The bug is low-impact
(the field is not used for any critical decision) but means the field is useless as a diagnostic
tool for understanding indexing latency.

---

## 7. `_canonical_json()` Duplication

Three copies exist in `captures/format.py`, `captures/service.py`, and used in
`captures/repository.py` indirectly. This is minor but represents drift risk: if a future change
needs to alter the canonical serialization (e.g., for performance), three locations must be
updated.

---

## 8. `websockets` Range is Too Wide

The dependency `websockets>=14,<16` spans two major versions. websockets 15 introduced breaking
changes to its high-level API. Narrowing to `>=14,<15` would be safer.

---

## 9. `basedpyright` Coverage Partial

Type checking is only enforced for `core/` and `shared/`. The capture engine, association
network handler, and replay service are not statically type-checked. Given that these components
are the most complex and concurrency-sensitive, extending type checking here would catch
real errors.
