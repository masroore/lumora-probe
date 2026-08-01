# Recommendations

Prioritised, actionable improvements ordered by engineering impact. Each item references the
relevant finding(s) and includes concrete implementation guidance.

---

## Priority 1 — Before Any Deployment Expansion

### R-01 · Wire LifecycleManager in bootstrap.py (F-001)

**What:** Integrate `LifecycleManager` into the production ASGI application so that graceful
shutdown, drain-before-close, and startup sweep are guaranteed.

**How:**
```python
# In build_production_app(), add:
from lumora_probe.core.lifecycle import LifecycleManager

lifecycle = LifecycleManager(shutdown_grace_seconds=config.shutdown_grace_seconds)
lifecycle.register(bus_service_adapter)  # wraps EventBus
lifecycle.register(capture_engine)  # CaptureEngine
lifecycle.register(dicom_listener)  # DICOMListener
lifecycle.register(replay_runtime_adapter)  # ReplayRuntime


@asynccontextmanager
async def lifespan(app: FastAPI):
    await lifecycle.start()
    await replay_runtime.startup()
    yield
    await lifecycle.shutdown()


app = FastAPI(lifespan=lifespan)
```

The `LifecycleManager.shutdown()` already handles `stop_accepting → drain → flush → stop`
in order. `ReplayRuntime.startup()` performs the job sweep. Both already exist; they just
need wiring.

**Effort:** 2–4 hours.

---

### R-02 · Expose `drain()` on `EventSubscription` (F-002)

**What:** Remove the private `_queue.join()` call in `CaptureEngine.drain()`.

**How:**
```python
# In core/bus.py, EventSubscription:
async def join(self) -> None:
    """Wait for all queued events to be consumed."""
    if self.callback is not None:
        raise RuntimeError("callback subscriptions do not expose a queue join")
    await self._queue.join()


# In captures/service.py, CaptureEngine.drain():
async def drain(self) -> None:
    if self._subscription is not None:
        await self._subscription.join()
```

**Effort:** 30 minutes.

---

### R-03 · Apply executor_workers to the asyncio default executor (F-011)

**What:** Make `StartupConfig.executor_workers` actually control thread pool size.

**How:** In the ASGI lifespan startup:
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

loop = asyncio.get_running_loop()
loop.set_default_executor(
    ThreadPoolExecutor(
        max_workers=config.executor_workers,
        thread_name_prefix="lumora-worker",
    )
)
```

This should be the first action in the lifespan context manager, before any service starts.

**Effort:** 30 minutes.

---

## Priority 2 — Correctness Fixes

### R-04 · Fix `CaptureEngine.stop_session()` session-pop ordering (F-006)

**What:** Prevent events from being written to a session after it is being sealed.

**How:** Pop the session reference from `_sessions` immediately after drain #1, retaining a
local reference for sealing:

```python
async def stop_session(self, capture_id: str) -> CaptureManifest:
    session = self._sessions.pop(capture_id)  # pop early
    session.capture.stop()
    await self._publish_lifecycle("CaptureStopped", capture_id, {...})
    await self.drain()
    session.capture.complete()
    await self._publish_lifecycle("CaptureCompleted", capture_id, {...})
    await self.drain()
    # no more events can route to this session; seal is safe
    session.writer.update_manifest(...)
    return session.writer.seal(completed_at=self.clock.now())
```

**Effort:** 1 hour including test.

---

### R-05 · Fix `RetentionPolicy.select()` byte-budget algorithm (F-004)

**What:** Stop silently skipping captures that don't fit within the byte budget.

**How:**
```python
for record in retained:
    size = sum(item.size for item in record.objects)
    if total + size > self.max_bytes:
        break  # stop retaining; everything from here is older
    size_limited.append(record)
    total += size
retained = size_limited
```

Add a test that verifies: given captures with sizes [80, 30, 5] and max_bytes=100, only the
80-byte capture is retained (the 30 doesn't fit, so stop).

**Effort:** 1 hour.

---

### R-06 · Fix `execute_read()` read_only condition (F-007)

**What:** Always open a read-only connection for read queries.

**How:**
```python
async def execute_read(self, sql: str, parameters: Sequence[Any] = ()) -> list[sqlite3.Row]:
    def read() -> list[sqlite3.Row]:
        with self.connection(read_only=True) as connection:  # always read-only
            return list(connection.execute(sql, parameters).fetchall())

    return await asyncio.to_thread(read)
```

**Effort:** 15 minutes.

---

### R-07 · Fix `store_c_store()` error code (F-010)

**What:** Return the correct DICOM status code for dataset parse failures.

**How:**
```python
except (AttributeError, TypeError, ValueError):
    return 0x0110   # Processing Failure, not Out of Resources
except OSError:
    return 0xA700   # Out of Resources is appropriate for I/O failures
```

**Effort:** 15 minutes.

---

### R-08 · Fix `indexed_at` to use current clock time (F-013)

**How:**
```text
indexed_at=self.clock.now(),   # was: manifest.created_at
```

**Effort:** 5 minutes.

---

## Priority 3 — Performance

### R-09 · Store object sizes in instances table (F-008)

**What:** Eliminate the O(n×m) stat() calls in `list_captures()`.

**How:**
1. Add `size INTEGER NOT NULL DEFAULT 0` to the `instances` table schema.
2. Populate it in `_write_record()`.
3. Read it directly in `list_captures()` without calling `stat()`.

This requires a schema migration. Since `index.db` is rebuildable, the migration can be a
`recreate_index_schema()` call on version bump.

**Effort:** 2–3 hours.

---

### R-10 · Defer `rebuild_study_projection()` to end of `rebuild()` (F-009)

**How:**
```python
async def rebuild(self, primary_root, *, additional_roots=()):
    packages = discover_capture_packages(primary_root, additional_roots=additional_roots)
    await asyncio.to_thread(self.databases.index.initialise)
    records = []
    for package, source_root in packages:
        package = await self.recover_package(package)
        # index without study rebuild
        records.append(await self._index_no_study_rebuild(package, source_root=source_root))
    # one final study rebuild
    await asyncio.to_thread(self._rebuild_studies_once)
    return tuple(records)
```

**Effort:** 2 hours.

---

## Priority 4 — Technical Debt Reduction

### R-11 · Implement `associations/service.py` (F-003)

**What:** Create `AssociationService` with listener lifecycle, allowlist management, and
health reporting.

**How:** Define `AssociationService` with:
- `start()` / `stop()` delegating to `DICOMListener`
- `health()` delegating to `DICOMListener.health()`
- `update_allowlist(aets: frozenset[str])` rebuilding and restarting the listener

Register it with `LifecycleManager` in `bootstrap.py`.

**Effort:** 4–8 hours.

---

### R-12 · Extend basedpyright to captures, associations, replay (F-021)

**How:**
```toml
[tool.basedpyright]
include = [
    "src/lumora_probe/core",
    "src/lumora_probe/shared",
    "src/lumora_probe/captures",
    "src/lumora_probe/associations",
    "src/lumora_probe/replay",
]
typeCheckingMode = "strict"
```

Fix any type errors that surface. The annotation quality in these modules appears sufficient
to support strict checking.

**Effort:** 2–4 hours.

---

### R-13 · Extract `_canonical_json()` and `_identity()` to shared utilities (F-014, F-015)

**How:**
- Move `_canonical_json()` to `core/` as `core/json.py` or add to `core/storage.py` as a
  standalone function.
- Move `_identity()` to `shared/errors.py` alongside `domain_invariant()`.
- Update imports in the three files that currently duplicate it.

**Effort:** 1 hour.

---

### R-14 · Move `is_uuid7()` to `core/ids.py` (F-018)

**How:**
1. Add `is_uuid7()` to `core/ids.py`.
2. Import from `core/ids.py` in `core/config.py`, `captures/format.py`, and `shared/events.py`.
3. Run import-linter to confirm boundaries are not violated.

**Effort:** 30 minutes.

---

### R-15 · Narrow dependency ranges (F-016, F-017)

**How:**
```toml
"websockets>=14,<15",       # was >=14,<16
"pytest>=9.0,<10.0",        # was >=9.0
"ruff>=0.12,<1.0",          # was >=0.12
```

**Effort:** 15 minutes.

---

### R-16 · Refactor `MetricRegistry._counter()` special case (F-005)

**How:**
```python
def _counter(self, name: str, **labels: str) -> None:
    key = (name, _labels(labels))
    self._counters[key] += 1


def _counter_by(self, name: str, amount: int, **labels: str) -> None:
    key = (name, _labels(labels))
    self._counters[key] += amount
```

Replace the single `_counter("events.dropped", amount=dropped)` call with
`_counter_by("events.dropped", int(dropped))`.

**Effort:** 30 minutes.

---

## Priority 5 — Testing Gaps

### R-17 · Add adversarial test for shutdown mid-active-capture

Write a component test that:
1. Starts the event bus and capture engine.
2. Begins a capture session.
3. Publishes 10 events.
4. Calls `lifecycle.shutdown()` while 5 events are still in-flight.
5. Verifies that `CaptureInterrupted` is written to the manifest.
6. Verifies the events.jsonl contains a contiguous sequence up to the interrupt point.

**Effort:** 3–4 hours (requires lifecycle wiring first, R-01).

---

### R-18 · Add test for `RetentionPolicy` byte-budget overflow behavior

Write a unit test that:
- Creates captures of sizes [80, 30, 5] with `max_bytes=100`.
- Calls `policy.select(records)` and verifies the 30-unit capture is NOT retained.

This test will currently fail if the fix in R-05 has not been applied (confirming the bug).

**Effort:** 30 minutes.
