# Findings

All findings ranked by severity. Each finding includes evidence, architectural impact,
operational impact, and recommendation.

---

## Critical

### F-001 · `bootstrap.py` does not wire LifecycleManager — graceful shutdown is absent

**Severity:** Critical  
**Component:** Bootstrap / Composition Root  
**File:** `src/lumora_probe/bootstrap.py`

**Description:**  
`build_production_app()` creates the event bus, plugin service, storage, and audit log, but
does not instantiate a `LifecycleManager` or register any of these services. The production
application has no managed shutdown sequence. When the ASGI server terminates, the event bus,
capture engine, and DICOM listener are not drained or stopped.

**Evidence:**  
`bootstrap.py` lines 98–178: no `LifecycleManager`, no `LifecycleManager.register()`, no ASGI
`lifespan` context manager. `core/lifecycle.py` defines the correct primitive.

**Architectural impact:**  
Violates the shutdown contract in CLAUDE.md: *"stop accepting associations → drain ingress →
flush/fsync the capture writer → close, within a bounded grace period."* The `CaptureInterrupted`
event specified for deadline violations is never written.

**Operational impact:**  
Active capture sessions at shutdown are left without `CaptureInterrupted` markers. On restart,
`CaptureRepository.rebuild()` and `recover_package()` will detect and heal torn JSONL, but only
if triggered by a rebuild. Jobs marked `running` in `app.db` are never swept to `interrupted`
at startup unless `ReplayRuntime.startup()` is called, which requires wiring.

**Recommendation:**  
Create a `LifecycleManager` in `build_production_app()`. Register `EventBus`, `CaptureEngine`,
`DICOMListener`, and `ReplayRuntime` in dependency order. Attach to a FastAPI `lifespan`
async context manager that calls `manager.start()` on enter and `manager.shutdown()` on exit.

**Implementation priority:** High — before any deployment where capture integrity matters.

---

### F-002 · `CaptureEngine.drain()` accesses `EventSubscription._queue` directly

**Severity:** Critical  
**Component:** Capture Engine  
**File:** `src/lumora_probe/captures/service.py`, line 454

**Description:**  
```python
async def drain(self) -> None:
    if self._subscription is not None:
        await self._subscription._queue.join()
```
`_queue` is a private attribute of `EventSubscription`. The public API exposes `get()`,
`get_nowait()`, and `task_done()` but no `drain()` or `join()`. This bypasses the public
contract.

**Evidence:**  
`captures/service.py:454`, `core/bus.py:107–117` (public API of `EventSubscription`).

**Architectural impact:**  
If `EventSubscription` is refactored (e.g., to support batched delivery or a different
backpressure mechanism), this call silently breaks without compile-time detection.

**Operational impact:**  
Currently harmless since `asyncio.Queue.join()` is stable. The risk is in future refactoring.

**Recommendation:**  
Add `async def join(self) -> None` to `EventSubscription` that delegates to `self._queue.join()`,
or expose `async def drain(self) -> None` on `EventSubscription`. Remove the private access.

**Implementation priority:** Medium.

---

## High

### F-003 · `associations/service.py` is an empty stub

**Severity:** High  
**Component:** Associations Slice  
**File:** `src/lumora_probe/associations/service.py`

**Description:**  
The file contains only `__all__: tuple[str, ...] = ()`. No `AssociationService` exists.
The `DICOMListener` in `associations/network.py` is substantial, but there is no service layer
to wire it to captures, expose history, manage allowlists, or register lifecycle health.

**Evidence:**  
`src/lumora_probe/associations/service.py` line 1: single-line stub.
`bootstrap.py` creates no association service.

**Architectural impact:**  
The associations slice is architecturally incomplete. The composition root has no path to start
the DICOM listener, subscribe it to captures, or surface association lifecycle events via the
bus in a structured way.

**Operational impact:**  
At v0.1.0 engineering deployments may work if `DICOMListener` is wired directly in bootstrap
(which it appears not to be), but any feature that requires association-level context
(allowlist management, per-association replay trigger, association history API) has no service
layer.

**Recommendation:**  
Implement `AssociationService` with at minimum: `start_listener()`, `stop_listener()`,
`health()`, and the wiring to publish association lifecycle events to the bus. Document in
CLAUDE.md if this is intentionally deferred to a future phase.

**Implementation priority:** High.

---

### F-004 · `RetentionPolicy.select()` byte-budget skips captures non-deterministically

**Severity:** High  
**Component:** Capture Repository  
**File:** `src/lumora_probe/captures/repository.py`, lines 69–87

**Description:**  
The byte-budget loop skips a capture if `total + size > max_bytes`, then continues checking
smaller captures. This produces a non-monotonic result: captures are not retained by recency
order when the byte limit is active, and a large recent capture can be evicted while a smaller
older capture is kept.

**Evidence:**  
```python
if total + size > self.max_bytes:
    continue
```
Consider: max_bytes=100, sizes (newest first) [80, 30, 5].
- 80: 80 ≤ 100 → retained (total=80)
- 30: 110 > 100 → **skipped**
- 5: 85 ≤ 100 → retained (total=85)

Result: captures of size 80 and 5 are retained, but the 30-unit capture (second most recent)
is evicted. The expected behavior for a recency-first byte budget is: retain 80, then the
30-unit capture doesn't fit and everything smaller is also excluded.

**Architectural impact:**  
Data retention semantics are not what operators expect. A large capture from this morning
may be retained while a medium capture from this morning is evicted.

**Operational impact:**  
Silent incorrect data retention. Operators may observe captures missing without any indication
of why.

**Recommendation:**  
Change the byte-budget loop to stop at the first capture that doesn't fit, rather than
continuing:
```python
for record in retained:
    size = sum(item.size for item in record.objects)
    if total + size > self.max_bytes:
        break  # stop, not continue
    size_limited.append(record)
    total += size
```

**Implementation priority:** Medium.

---

### F-005 · `MetricRegistry._counter()` special-case `amount` is fragile

**Severity:** High  
**Component:** Metrics  
**File:** `src/lumora_probe/core/metrics.py`, lines 186–188

**Description:**  
```python
def _counter(self, name: str, **labels: str | float) -> None:
    key = (name, _labels(labels))
    self._counters[key] += 1 if name != "events.dropped" else int(labels.pop("amount", 1))
```
The counter increment amount is special-cased by name. Only `events.dropped` uses the `amount`
label to increment by more than 1. The `_labels()` function also filters out `amount` as a
special key. This creates an undocumented convention: any call to `_counter("events.dropped",
amount=N)` increments by N; any other counter ignores `amount`.

**Evidence:**  
`core/metrics.py:186–188` and `_labels()` at line 206–207.

**Architectural impact:**  
Adding a second counter that needs batch increments requires understanding and replicating
this hidden convention. The `amount` key is implicitly reserved but not declared as such.

**Operational impact:**  
Low direct impact; the behavior is correct. The risk is in maintenance.

**Recommendation:**  
Add a separate `_counter_by(name: str, amount: int, **labels: str) -> None` method for batch
increment. Remove the name-based special case from `_counter()`.

**Implementation priority:** Low.

---

### F-006 · `CaptureEngine.stop_session()` double-drain with interleaved publish

**Severity:** High  
**Component:** Capture Engine  
**File:** `src/lumora_probe/captures/service.py`, lines 538–557

**Description:**  
```python
session.capture.stop()
await self._publish_lifecycle("CaptureStopped", ...)
await self.drain()          # drain 1
session.capture.complete()
await self._publish_lifecycle("CaptureCompleted", ...)
await self.drain()          # drain 2
...
sealed = session.writer.seal(...)
self._sessions.pop(capture_id)
```
Between drain #2 completing and `self._sessions.pop(capture_id)`, the capture session remains
in `_sessions`. Any event arriving from another coroutine or thread during this window will
be written to the `session.writer` after the manifest was already sealed (drain #2 caused
the worker to process all buffered events). After `seal()`, `_ensure_open()` will raise
`CaptureFormatError`, causing `_record_event` to fail silently (the exception is caught in
`deliver()`'s broad catch).

**Evidence:**  
`captures/service.py:538–557` (stop_session), `captures/service.py:750–757` (_consume→_record_event),
`captures/format.py:357–364` (_ensure_open raises after seal).

**Architectural impact:**  
The capture session lifecycle is not atomically protected. Events can arrive between seal and
pop.

**Operational impact:**  
Events that arrive after drain #2 but before the session is popped are silently dropped.
The `events.jsonl` may be incomplete. The sealed manifest says `state=completed` but the
bus sequence may have gaps.

**Recommendation:**  
Pop the session from `_sessions` *before* calling `drain()` on the second drain, then drain
and seal independently. Or take a snapshot of the writer reference before the pop, so the
worker never sees a popped session that still has events in the queue.

**Implementation priority:** Medium.

---

## Medium

### F-007 · `execute_read()` conditionally opens a write-capable connection

**Severity:** Medium  
**Component:** Storage  
**File:** `src/lumora_probe/core/storage.py`, line 242

**Description:**  
```python
with self.connection(read_only=self.path.exists()) as connection:
```
If the database file is missing, a write-capable connection is opened for a read query. This
silently creates an empty database on a read call.

**Recommendation:**  
Always pass `read_only=True` for `execute_read()`. Let SQLite raise a missing-file error.

---

### F-008 · `CaptureRepository.list_captures()` makes O(n×m) `stat()` calls in executor

**Severity:** Medium  
**Component:** Capture Repository  
**File:** `src/lumora_probe/captures/repository.py`, line 175

**Description:**  
For large repositories, `stat()` calls for every object of every capture can block the
executor thread for tens of seconds.

**Recommendation:**  
Store object sizes in the `instances` table at index time. Add a `size INTEGER NOT NULL DEFAULT 0`
column to `instances`. Remove the `stat()` call from `list_captures()`.

---

### F-009 · `rebuild_study_projection()` called per-capture during rebuild (O(n²) churn)

**Severity:** Medium  
**Component:** Capture Repository  
**File:** `src/lumora_probe/captures/repository.py`, line 292

**Description:**  
Each `_write_record()` call triggers a full study/series delete-and-recompute.

**Recommendation:**  
Call `rebuild_study_projection()` once after all `_write_record()` calls in `rebuild()`.

---

### F-010 · `store_c_store()` returns wrong error code on parse failure

**Severity:** Medium  
**Component:** CaptureEngine / DICOM  
**File:** `src/lumora_probe/captures/service.py`, line 722–741

**Description:**  
Returns `0xA700` (Out of Resources) for dataset parse errors. Should return `0x0110`
(Processing Failure).

**Recommendation:**  
Return `0x0110` for `AttributeError`/`TypeError`/`ValueError` (parse errors). Reserve
`0xA700` for actual resource-exhaustion conditions.

---

### F-011 · `executor_workers` config has no effect on `asyncio.to_thread()`

**Severity:** Medium  
**Component:** Configuration / Startup  
**File:** `src/lumora_probe/core/config.py`, `src/lumora_probe/bootstrap.py`

**Description:**  
`StartupConfig.executor_workers` is validated but never applied to the asyncio event loop's
default executor.

**Recommendation:**  
In the application lifespan startup, call
`asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=config.executor_workers))`.

---

### F-012 · `DICOMListener._state_for()` creates a new ID on association miss

**Severity:** Medium  
**Component:** DICOM Listener  
**File:** `src/lumora_probe/associations/network.py`, lines 697–709

**Description:**  
If an event handler is called for an association not in `_states`, a new random ID is assigned
silently. Multiple misses for the same association produce different IDs, breaking correlation.

**Recommendation:**  
Log a warning when the state lookup fails and return a fallback with a fixed "unknown" ID
that is clearly identifiable in the event stream.

---

## Low

### F-013 · `indexed_at` always equals `created_at`

**Severity:** Low  
**Component:** Capture Repository  
**File:** `src/lumora_probe/captures/repository.py`, line 258

**Recommendation:** Use `self.clock.now()` for `indexed_at`.

---

### F-014 · `_canonical_json()` duplicated in three files

**Severity:** Low  
**Component:** Capture layer  
**Files:** `captures/format.py`, `captures/service.py`

**Recommendation:** Extract to `core/` or `shared/` as a single utility function.

---

### F-015 · `_identity()` duplicated in `captures/domain.py` and `associations/domain.py`

**Severity:** Low  
**Component:** Domain layer

**Recommendation:** Extract to `shared/errors.py` or `shared/value_objects.py`.

---

### F-016 · `websockets` range spans two major versions

**Severity:** Low  
**Component:** Dependencies

**Recommendation:** Change to `websockets>=14,<15`.

---

### F-017 · `pytest` and `ruff` have no upper version bounds

**Severity:** Low  
**Component:** Dev dependencies

**Recommendation:** Add `<10.0` to `pytest`, `<1.0` to `ruff`.

---

### F-018 · `is_uuid7()` defined in `core/config.py` but used across unrelated modules

**Severity:** Low  
**Component:** Core utilities

**Recommendation:** Move to `core/ids.py`.

---

## Informational

### F-019 · `orjson` referenced in CLAUDE.md but absent from `pyproject.toml`

**Severity:** Informational  
**Component:** Dependencies

If `orjson` is intended as an optimization, it should be added as a dependency or removed
from the toolchain description.

---

### F-020 · `EventBus` auto-starts on first publish

**Severity:** Informational  
**Component:** Event Bus

Convenient but undocumented. Should be noted in the class docstring.

---

### F-021 · `basedpyright` coverage limited to `core/` and `shared/`

**Severity:** Informational  
**Component:** Type checking

Extending to `captures/`, `associations/`, `replay/` would provide static correctness
guarantees for the most complex components.

---

## Finding Count Summary

| Severity | Count |
|---|---|
| Critical | 2 |
| High | 4 |
| Medium | 6 |
| Low | 6 |
| Informational | 3 |
| **Total** | **21** |
