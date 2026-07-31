# Architecture Review

## 1. Slice Layout and Package Boundaries

The repository implements the documented module-first slice layout:

```
core/          shared/        captures/      associations/
analysis/      replay/        reports/       plugins/
settings/      web/
```

Every slice contains `domain.py`, `service.py`, `repository.py`, `api.py`, and `contracts.py`.
This is exactly the structure specified in `CLAUDE.md` and the baseline documents.

Import-linter contracts are present in `pyproject.toml` and the test
`test_import_boundaries.py` exercises them. The boundary rules as stated in `CLAUDE.md` are:

- `core` imports no slice — **verified**: `core/` files import only stdlib, pydantic-settings,
  and `shared/events.py` (through `bus.py`). This is a minor boundary concern; see §4.
- `shared` imports only `core` — **verified**.
- Slices may import `core`, `shared`, and other slices' `contracts.py` only —
  **verified** in read files. `replay/service.py` imports `associations/contracts.py`
  (`DICOMDatasetSender`, `DICOMStoreResult`) correctly through the public contracts path.
- `web` imports slices; no slice imports `web` — **verified**.
- No `domain.py` imports FastAPI, SQLAlchemy, or Jinja — **verified** in all read files.

**Finding:** `core/metrics.py` imports `shared/events.py` at module level (for
`DEFAULT_EVENT_REGISTRY` inside `event_category()`). The import is deferred to function scope to
avoid a circular import, but `core/metrics.py` defines `MetricRegistry` which subscribes to the
bus using `shared.events.EventEnvelope`. The `CLAUDE.md` contract says `core` must not import
slice packages; `shared` is not a slice, so this is technically within the letter of the rules.
However, `core/metrics.py` functionally depends on `shared/events.py`'s `DEFAULT_EVENT_REGISTRY`
which is initialized at import time. This creates an implicit ordering dependency that is hidden
behind a deferred import. Not a violation, but worth documenting.

---

## 2. Concurrency Model

The architecture mandates a single process, one asyncio loop, and exactly one thread boundary:
pynetdicom threads → `loop.call_soon_threadsafe`.

**Implementation:**

- `EventBus.publish_from_thread()` calls `asyncio.run_coroutine_threadsafe()` which wraps
  `call_soon_threadsafe`. This is correct.
- `DICOMListener` event handlers (`_on_requested`, `_on_accepted`, etc.) all call
  `self.event_ingress.publish_from_thread(event)` — never `asyncio.run()` or direct loop access.
  The thread boundary is honoured.
- `DICOMListener` holds a `threading.Lock` for `_states` and `_pdu_stats` which is the correct
  mutual exclusion mechanism for shared state accessed from both pynetdicom threads and
  potential inspect calls.
- All blocking work (dataset parse, SQLite writes, report generation) uses `asyncio.to_thread()`
  or the `ExecutorPool.run()` façade. Both are correct.

**Concern — `CaptureEngine._consume()` loop:**

```python
async def _consume(self) -> None:
    assert self._subscription is not None
    while True:
        event = await self._subscription.get()
        try:
            await asyncio.to_thread(self._record_event, event)
        finally:
            self._subscription.task_done()
```

`_record_event` calls `self.ring_buffer.record_event(event)` which calls `self._append(record)`
which acquires `self._lock` (a `threading.RLock`). Acquiring an RLock from an executor thread is
correct, but `_append` also calls `self._rewrite()` which calls `os.fsync` in a hot path. A
single slow disk will stall the capture subscriber for the duration of every fsync, blocking the
queue drain. This is by design (the capture path must not drop), but the fsync is synchronous
inside the executor call — it will back-pressure the bus ingress queue. This is architecturally
correct behaviour; it just means fsync latency is visible as ingress pressure.

**Concern — `CaptureEngine.drain()` private access:**

```python
async def drain(self) -> None:
    if self._subscription is not None:
        await self._subscription._queue.join()
```

`_queue` is a private attribute of `EventSubscription`. The `EventSubscription` public API
exposes `get()`, `get_nowait()`, and `task_done()`. There is no `drain()` or `join()` on the
public interface. This bypasses encapsulation. If `EventSubscription` is refactored to use a
different internal structure (e.g., a deque with a separate event), this call silently breaks.

**Recommendation:** Expose `async def drain() -> None` or `async def join() -> None` on
`EventSubscription`.

---

## 3. Lifecycle Management

`core/lifecycle.py` provides `LifecycleManager` with ordered startup, reverse shutdown,
drain/flush steps, and a bounded grace period. This is the specified mechanism.

**Critical gap — `bootstrap.py` does not use `LifecycleManager`:**

`build_production_app()` creates `EventBus`, `PluginService`, `HealthRegistry`,
`StorageDatabases`, `AuditLog`, and `AlertRegistry`, but **none of these are registered with a
`LifecycleManager`**. There is no `LifecycleManager` instance in `bootstrap.py` at all.

Consequence: the production FastAPI application has no guaranteed shutdown order. The ASGI server
will call its own shutdown hook, but:

- `EventBus.stop()` (which drains all enqueued events) is not called.
- `CaptureEngine.stop()` (which writes `CaptureInterrupted`) is not called.
- `DICOMListener.stop()` is not called.
- `ReplayRuntime` startup sweep (interrupt-running-jobs) is not invoked.

The specification requires: *"stop accepting associations → drain ingress → flush/fsync the
capture writer → close, within a bounded grace period."* This contract exists in the code but is
not wired to any production exit path.

**Recommendation:** Create a `LifecycleManager` in `build_production_app()`, register all
services in dependency order, and attach it to the FastAPI `lifespan` context manager.

---

## 4. Event Envelope Design

`EventEnvelope` in `shared/events.py` is a Pydantic v2 `BaseModel` with `extra="allow"` and
`frozen=True`. This correctly implements the byte-faithful persistence contract: unknown fields
are preserved. The `with_sequence()` method returns a copy with the sequence assigned; sequencing
happens at publish time on the bus, not at creation time. This matches ADR-0017.

The payload registry validates known events and accepts unknown `(event_name, event_version)`
pairs as `UnknownEventPayload` — forward-compatible by design.

`EventEnvelope.create()` raises if clock or id_generator is None. This is the correct guard; it
prevents accidentally creating envelope with implicit time.

**Concern — `event_name` command-form guard:**

```python
_RESERVED_IMPERATIVE_PREFIXES = (
    "Start", "Stop", "Accept", "Reject", "Release", "Abort", "Parse", "Load",
    "Do", "Request", "Create", "Delete", "Update", "Set",
)
```

The guard only fires when the prefix is followed by an uppercase letter
(`value[len(prefix)].isupper()`). `"Started"` passes because `value[5] == 'e'` is not upper.
This is intentional (past-tense forms are allowed). However `"SetCompleted"` would also pass
(prefix is `"Set"`, next char is `"C"` — wait, that fails). Actually this is fine as stated;
the prefix list blocks `"SetX"` style imperative naming. The guard is correct.

---

## 5. Storage Architecture

Two physical databases with distinct authority — `index.db` (rebuildable) and `app.db`
(authoritative) — matches ADR-0023. Schema is embedded in `core/storage.py` as literal SQL
strings, applied idempotently via `CREATE TABLE IF NOT EXISTS`. The index schema uses
`recreate_index_schema()` (DROP and recreate) while the app schema uses `migrate_app_schema()`
(additive). This asymmetry is correct given the different authority roles.

**Concern — `execute_read()` read_only flag logic:**

```python
async def execute_read(self, sql: str, parameters: Sequence[Any] = ()) -> list[sqlite3.Row]:
    def read() -> list[sqlite3.Row]:
        with self.connection(read_only=self.path.exists()) as connection:
```

The `read_only` flag passed to `connection()` depends on `self.path.exists()` at call time.
If the database file does not yet exist, `read_only=False` is used even for read queries.
This is harmless in practice (the write connection will create the file), but the condition
is semantically wrong: the intent is "use read-only URI if possible", not "check existence".
A non-existent file is a setup error that should surface earlier, not silently fall back to
writable mode during a read.

**Concern — `write_transaction()` uses `threading.RLock`:**

The lock is per-`SQLiteDatabase` instance. With `asyncio.to_thread()`, each write spawns a
thread, which acquires the RLock. An RLock is re-entrant within the *same thread*, but from
different executor threads it provides mutual exclusion. However, `asyncio.to_thread()` does not
guarantee the same thread is reused across calls. The RLock is used correctly as a mutex here
(not as a re-entrancy mechanism), but an `asyncio.Lock` would better express intent for
loop-side ownership. This is a low-priority style issue because all writes go through
`to_thread()`.

---

## 6. Configuration Architecture

`StartupConfig` uses `pydantic-settings` with `env_prefix="LUMORA_"` and `frozen=True`.
Configuration tiers (env > .env > TOML/YAML > defaults) are correctly implemented in
`load_startup_config()`.

The custom YAML parser (`_parse_simple_yaml`) deliberately rejects nested YAML. This is the
correct trade-off: avoid adding PyYAML as a runtime dependency while supporting the flat config
subset most users need.

The network gate (`_validate_network_gate()`) is called after config construction and raises
`NetworkExposureError` if a non-loopback bind is attempted without
`allow_unauthenticated_network=True`. This is correct and enforced at startup.

**Note:** `is_uuid7()` is defined in `core/config.py` but is used across multiple modules
(`captures/format.py`, `shared/events.py`, `core/paths.py`). This is a minor cohesion issue;
the function belongs in `core/ids.py` or a utilities module. It is currently imported from
`config.py` by modules that have no other reason to import config.

---

## 7. Client-Asserted Event Quarantine

The bus enforces the quarantine rule:

```python
if event.origin is EventOrigin.CLIENT_ASSERTED and (
    category is not EventCategory.VIEWER or event.producer != "web-ui"
):
    raise ValueError(
        "client-asserted events must be registered Viewer events produced by web-ui"
    )
```

This check fires at publish time on the loop, before sequencing. The registry must know the
category; unknown event names will return `None` from `category_for()`, which evaluates as
`None is not EventCategory.VIEWER` → `True`, so unknown client-asserted events are rejected.
This is the correct fail-closed behavior.

---

## 8. Summary of Architecture Compliance

| Rule | Verdict | Notes |
|---|---|---|
| Slice layout | ✅ | All slices present with correct internal structure |
| Import boundaries | ✅ | Verified in all read files |
| Single thread boundary | ✅ | `publish_from_thread` is the only crossing |
| Backpressure split | ✅ | Capture never drops, UI drops-oldest |
| No ORM | ✅ | Hand-written row↔domain mapping |
| Clock/ID injection | ✅ | `time.`/`uuid.` only in `core/` |
| Sequencing authority | ✅ | Bus assigns sequence at publish time |
| Data-dir version marker | ✅ | Reject-on-newer enforced |
| Network filesystem rejection | ✅ | `assert_local_filesystem` present |
| LifecycleManager at production | ❌ | Not wired in `bootstrap.py` |
| Service drain on shutdown | ❌ | Not called in any ASGI lifespan hook |
| `associations/service.py` | ❌ | Empty stub |
