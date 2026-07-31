# Performance Review

## 1. Hot Paths

### 1.1 Event Dispatch Loop

`EventBus._dispatch()` iterates all subscribers for every event:

```python
async def _dispatch(self, event: EventEnvelope) -> None:
    for subscription in tuple(self._subscribers.values()):
        if subscription.closed:
            continue
        if subscription.callback is None and subscription.channel is SubscriberChannel.UI:
            subscription.enqueue_ui(event)
            continue
        await subscription.deliver(event, self.subscriber_budget_seconds)
```

`tuple(self._subscribers.values())` creates a copy of the subscriber list on every event. For a
system with 2–5 subscribers this is negligible. For large subscriber counts (not expected) it
would be a hot allocation. In the current deployment model this is acceptable.

`deliver()` measures elapsed time using `self._bus.clock.monotonic_ns()` — two clock reads per
subscriber per event. Again negligible for current subscriber counts.

### 1.2 JsonlWriter re-opens the file on every append

```python
def append_raw(self, raw: bytes) -> None:
    ...
    with self.path.open("ab") as handle:
        handle.write(line)
        if self.fsync_policy is not FsyncPolicy.NEVER:
            handle.flush()
        if self.fsync_policy is FsyncPolicy.ALWAYS:
            os.fsync(handle.fileno())
```

`JsonlWriter.append_raw()` opens, writes, optionally fsyncs, and closes the file on every call.
With `FsyncPolicy.ALWAYS` (the default), this is:

- One `open()` syscall
- One `write()` syscall
- One `flush()` syscall
- One `fsync()` syscall (blocks until disk commits)
- One `close()` syscall

For a high-frequency DICOM capture with hundreds of events per second, each event incurs 5
syscalls plus a disk fsync. This will saturate any NVMe at roughly 100k IOPS ÷ 5 = ~20k
events/second ceiling. For spinning disk this drops to ~200 events/second.

More importantly: `CaptureEngine._consume()` calls `asyncio.to_thread(self._record_event, event)`
for each event. `_record_event` calls `session.writer.append_event_raw(event.to_json_bytes())`
which instantiates a new `JsonlWriter` and opens the file. Each event dispatch spawns a thread.

For high-frequency captures, thread creation overhead (even with the thread pool) and per-event
fsync will be the dominant cost. A write-batch accumulator with a configurable flush interval
would allow orders-of-magnitude higher throughput.

**Note:** This is a known trade-off and consistent with the architecture's durability-over-speed
stance for the capture path. FsyncPolicy.FLUSH and FsyncPolicy.NEVER exist as relaxed options.
The concern is whether the default is appropriate for all deployments.

**Severity:** Medium (performance, not correctness; by-design but worth surfacing).

### 1.3 `CaptureRepository.list_captures()` N×M stat() calls

Described in the correctness review. For 1000 captures × 100 objects, this is 100,000 `stat()`
calls in a single `asyncio.to_thread()` block. This will take 10–100 seconds on a slow filesystem
and blocks the single executor thread for that duration, preventing other database work.

**Severity:** Medium.

### 1.4 `rebuild_study_projection()` full delete-and-recompute on every index

Each `CaptureRepository.index()` call triggers:
```
DELETE FROM series;
DELETE FROM studies;
INSERT INTO studies ... (GROUP BY);
INSERT INTO series ... (GROUP BY);
```

For a rebuild of 500 captures, studies and series are deleted and recomputed 500 times. The
final state is correct, but the O(n²) SQL churn generates significant write amplification.

**Recommendation:** Accumulate all packages in memory, then call `_write_record()` followed by a
single `rebuild_study_projection()` at the end of `rebuild()`.

**Severity:** Medium.

---

## 2. SQLite Query Quality

### 2.1 Index coverage

The schema defines these indexes on `index.db`:

```sql
CREATE INDEX IF NOT EXISTS idx_captures_created_at ON captures(created_at);
CREATE INDEX IF NOT EXISTS idx_instances_study ON instances(study_uid);
CREATE INDEX IF NOT EXISTS idx_instances_series ON instances(study_uid, series_uid);
CREATE INDEX IF NOT EXISTS idx_instances_sop ON instances(sop_instance_uid);
CREATE INDEX IF NOT EXISTS idx_event_window_event_name ON event_window(capture_id, event_name);
```

The `list_captures()` query does `ORDER BY created_at, capture_id` — covered by
`idx_captures_created_at` (partially; capture_id is not in the index, so SQLite will use the
index for the created_at filter but may do a sort pass for the secondary column).

The `instances` join in `list_captures()` fetches ALL instances ordered by `capture_id,
instance_id`. There is no `LIMIT` clause. For a large repository this loads the entire instances
table into memory.

**Recommendation:** Paginate `list_captures()` at the API layer and add a `LIMIT`/`OFFSET`
to the instances query.

### 2.2 `projection_snapshot()` fetches entire tables without limits

```python
connection.execute("SELECT * FROM captures ORDER BY capture_id").fetchall()
connection.execute("SELECT * FROM studies ORDER BY study_uid").fetchall()
...
```

This is used for golden fixture comparison tests. Fine for tests, but should never be exposed
on a production API endpoint.

---

## 3. Memory Allocation

### 3.1 Ring buffer snapshot materializes all records

```python
def snapshot(self, ...) -> tuple[RingBufferRecord, ...]:
    return tuple(
        record for record in self._records
        if (start_utc is None or record.occurred_at >= start_utc)
        ...
    )
```

For a 2GB ring buffer (`max_bytes` default), a full snapshot could return gigabytes of data.
The records contain the raw event bytes; a full snapshot allocates a new tuple of all matching
records. For the ring buffer promotion path this is necessary, but callers should be aware of
the allocation.

### 3.2 `RingBufferService._rewrite()` writes the entire buffer atomically

```python
def _rewrite(self) -> None:
    ...
    with temporary.open("wb") as handle:
        for record in self._records:
            handle.write(_ring_json(record))
```

Every time a record is expired (by time or by size), the entire ring buffer is rewritten to disk.
For a 2GB ring buffer with continuous expiry (steady-state DICOM traffic), this is a continuous
2GB write. `_ring_json()` serializes each record including its `raw` field as base64, which is
a 33% size inflation.

The `_append_persisted()` method handles the non-expiry case (append-only). The rewrite only
happens when records expire. For a ring buffer that never fills (short sessions), this is fine.
For a ring buffer under steady load, this is a significant I/O amplifier.

**Severity:** Low for normal use; Medium for long-running continuous capture.

---

## 4. Thread Pool Configuration

`executor_workers` defaults to 4. All blocking work (SQLite reads/writes, file I/O, pydicom
parsing) goes through `asyncio.to_thread()` which uses the default `ThreadPoolExecutor` (not
the `ExecutorPool` from `lifecycle.py` — which is defined but not wired in `bootstrap.py`).

`asyncio.to_thread()` uses the loop's default executor, which by default creates new threads up
to a limit. The `executor_workers` setting in `StartupConfig` exists but is not used to configure
the loop's default executor in `bootstrap.py`. This is another symptom of the missing lifecycle
wiring.

**Severity:** Medium (configuration drift; the setting exists but has no effect).
