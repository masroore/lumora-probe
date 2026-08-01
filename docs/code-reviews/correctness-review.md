# Correctness Review

## 1. EventBus

### 1.1 Capture channel queue size zero

```python
if active_size == 0 and active_channel is SubscriberChannel.UI:
    raise ValueError("queue_size must be positive for UI and non-negative for capture")
```

When `channel=CAPTURE` and `queue_size=None`, `active_size` is computed as `0` (the `if` branch
sets it to `ui_queue_size` only for UI). A queue with `maxsize=0` in Python means *unbounded*.
This is intentional for the capture channel (never drop), but it is not documented and the
comment in the guard only mentions UI. An unbounded capture queue means backpressure from a slow
capture writer will cause unbounded memory growth. The architecture says the capture path
*never drops*, which is correct, but the missing upper bound means OOM is possible under a very
slow disk with a very fast DICOM sender.

**Severity:** Medium. Behaviour matches specification; the bound-by-design is fine, but should
be called out explicitly.

### 1.2 `_clock_anomaly()` uses `event.occurred_at` subtraction

```python
wall_delta_ns = int((event.occurred_at - previous_wall).total_seconds() * 1_000_000_000)
```

`total_seconds()` returns a `float`. For durations longer than ~104 days, the nanosecond
conversion via float loses precision. The result will be rounded to the nearest microsecond.
For the intended use (sub-second divergence detection), this is harmless in practice. For
longer captures or cross-session clock anchoring, the float intermediate can silently lose ns
precision.

**Severity:** Low (informational for long-running captures).

### 1.3 `record_subscriber_failure` emits to `_diagnostics` without publishing

Subscriber failure events are appended to `self._diagnostics` (a plain list), not published
through the bus. This means they are visible via `bus.diagnostics` but do not trigger the
`EventsDropped` counter in `MetricRegistry`. The architecture says:
*"A capability that cannot be delivered is refused with an explanation, never silently degraded."*
These failures are not silently swallowed, but they are also not counted in the observable
metric surface. UI and downstream subscribers will not see `ErrorRaised` events from bus
subscriber failures.

**Severity:** Medium.

---

## 2. CaptureEngine

### 2.1 `stop_session()` double-drain race

```python
async def stop_session(self, capture_id: str) -> CaptureManifest:
    session = self._session(capture_id)
    session.capture.stop()
    await self._publish_lifecycle("CaptureStopped", ...)
    await self.drain()  # drain #1
    session.capture.complete()
    await self._publish_lifecycle("CaptureCompleted", ...)
    await self.drain()  # drain #2
    ...
    sealed = session.writer.seal(completed_at=self.clock.now())
    self._sessions.pop(capture_id)
```

After drain #1, `CaptureCompleted` is published and drain #2 waits for it to be processed by the
capture subscriber. The capture subscriber calls `_record_event()` which writes to
`session.writer`. However, between drain #2 completing and `session.writer.seal()` being called,
another publish could arrive (e.g., from a concurrent association). That event would be written
to the writer's JSONL file, but the session is already being sealed. If the `seal()` call
includes `completed_at`, but a later `_record_event` writes a line after the manifest is sealed,
the events.jsonl will have entries after the manifest was written.

More critically: `_sessions.pop(capture_id)` happens *after* `seal()`. If any of the lifecycle
publishes or drains are interrupted (e.g., by an asyncio cancellation), the session is left
dangling in `_sessions`.

**Severity:** Medium (race in edge case; cancellation leaves dangling session).

### 2.2 `_incomplete_aggregates()` checks event ordering, not event sets

```python
return tuple(
    aggregate_id
    for aggregate_id, names in grouped.items()
    if names[0] != "AssociationStarted"
    or names[-1] not in {"AssociationReleased", "AssociationAborted"}
)
```

This marks an aggregate incomplete if the *first* event is not `AssociationStarted` or the *last*
is not a terminal event. It does not check for gaps. An association where `AssociationStarted`
was captured, then `CStoreReceived` repeated, then the terminal event was not captured would
pass the check only on the terminal condition. This is likely correct for the intended heuristic,
but it is sensitive to the exact event names being prefixed with "Association". If a future event
name starts with "Association" but is not a lifecycle event, it could corrupt the check.

**Severity:** Low.

### 2.3 `store_c_store()` returns `0xA700` on parse error

```python
except (AttributeError, OSError, TypeError, ValueError):
    return 0xA700
```

`0xA700` is "Out of Resources". A parse error should return `0x0110` (Processing Failure) or
`0xC000` (Cannot Understand). Returning "Out of Resources" to the sender misrepresents the
failure reason. The sender may retry, which will produce another parse failure in a loop.

**Severity:** Medium.

---

## 3. CaptureRepository

### 3.1 `_write_record()` rebuilds entire study projection on every index

```python
rebuild_study_projection(connection)
```

`rebuild_study_projection()` deletes all study and series rows and recomputes from instances.
Called inside `_write_record()`, this runs on every `index()` call. During a full rebuild of
many captures, this is O(n²) in study-row churn: each of the n captures causes a full study
delete-and-recompute. For a repository with thousands of captures (possible in the ring-buffer
promotion use case), this is a performance bottleneck.

**Severity:** Medium (performance, not correctness).

### 3.2 `list_captures()` does `stat()` calls for each object inside a thread

```text
size=object_path.stat().st_size if object_path.is_file() else 0,
```

For a repository with 1000 captures × 100 objects each, this is 100,000 `stat()` calls inside
a single `asyncio.to_thread()` call. These are individual syscalls per object. For a large
repository this will take tens of seconds and block the executor thread.

**Severity:** Medium (scalability concern for large repositories).

### 3.3 `indexed_at` is set to `manifest.created_at` instead of clock time

```text
indexed_at=manifest.created_at,
```

`indexed_at` is semantically "when this capture was added to the index". Using `manifest.created_at`
makes it always equal to `created_at`, rendering `indexed_at` meaningless. The field should use
`self.clock.now()`.

**Severity:** Low.

---

## 4. StorageDatabases / SQLiteDatabase

### 4.1 `execute_read()` `read_only` logic is incorrectly conditioned on file existence

```python
with self.connection(read_only=self.path.exists()) as connection:
```

If the database file has been deleted externally, `self.path.exists()` returns `False` and a
write-capable connection is opened for a read query. This silently recreates the database (empty)
rather than raising an explicit error. The correct check is: always open read-only for read
queries, and let SQLite return an error if the file is missing.

**Severity:** Medium.

### 4.2 `recreate_index_schema()` uses multiple `executescript()` calls without proper isolation

```python
connection.executescript("DROP TABLE IF EXISTS event_window; DROP TABLE IF EXISTS instances;")
connection.executescript("DROP TABLE IF EXISTS series; DROP TABLE IF EXISTS studies;")
connection.executescript("DROP TABLE IF EXISTS captures; DROP TABLE IF EXISTS schema_metadata;")
connection.executescript(_INDEX_SCHEMA)
```

`executescript()` commits any pending transaction before executing and cannot be used within an
explicit transaction. If the process is killed between the DROP statements, the database is left
in a partially-destroyed state (some tables exist, some don't). For a rebuildable index this is
not catastrophic, but it means the rebuild after a crash will fail until a manual cleanup is done.

**Recommendation:** Wrap in a single `BEGIN EXCLUSIVE`/`COMMIT` using the `connection.execute()`
path, or use `executescript()` with a single script that includes all drops.

**Severity:** Low (index is rebuildable; crash-safety is partially provided by WAL).

---

## 5. RetentionPolicy

### 5.1 Byte-budget skip silently excludes captures

```python
if total + size > self.max_bytes:
    continue
```

This skips any capture whose cumulative size would exceed `max_bytes`, even if a smaller capture
later in the list would fit. Consider: max_bytes=100, captures of sizes [90, 5, 5]. After
selecting the 90-byte capture (total=90), the 5-byte captures are skipped (90+5=95 > 100 is
false, so actually they ARE included here). Wait — re-reading: `total + size > self.max_bytes` —
if total=90 and size=5, 95 > 100 is False, so the capture IS included. Let me re-examine with
max_bytes=100 and sizes [60, 60, 5]:

- retained = [60a, 60b, 5c] (most recent first after `reversed`)
- 60a: total=0+60=60, 60 > 100 → False → included; total=60
- 60b: total=60+60=120, 120 > 100 → True → **skipped**
- 5c: total=60+5=65, 65 > 100 → False → included; total=65

Result: [60a, 5c] are retained but 60b is skipped even though 60b+5c=65 ≤ 100. The algorithm
is greedy from most-recent, which means it can retain a small older capture while skipping a
large recent one that would still fit. This produces non-intuitive retention: not the most
recent N bytes, but a fragmented subset.

The architecture says `max_bytes` is a retention limit. The current algorithm does not implement
"retain as many recent captures as fit within max_bytes"; it implements "keep going through the
sorted list and skip anything that overflows, regardless of what follows".

**Severity:** Medium (data retention correctness).

---

## 6. MetricRegistry

### 6.1 `_counter()` special-cases `amount` inside label processing

```python
def _counter(self, name: str, **labels: str | float) -> None:
    key = (name, _labels(labels))
    self._counters[key] += 1 if name != "events.dropped" else int(labels.pop("amount", 1))
```

And `_labels()`:

```python
def _labels(labels: Mapping[str, str | int | float]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((key, str(value)) for key, value in labels.items() if key != "amount"))
```

Two problems:

1. `labels.pop("amount", 1)` modifies the `labels` dict that was passed as `**kwargs`. In Python,
   `**kwargs` creates a new dict, so this mutation is safe in isolation. But the `_labels()` call
   happens with the original (un-popped) `labels` since `_labels(labels)` is called before `+=`.
   The key therefore includes `amount` in its label tuple if Python evaluates left-to-right (which
   it does). Wait — the key computation `(name, _labels(labels))` happens before `labels.pop()`.
   `_labels()` explicitly filters out `amount`: `if key != "amount"`. So the key is correct. The
   `pop` is redundant but harmless. Still, the design is fragile and non-obvious.

2. This special case means that calling `self._counter("events.dropped", amount=5)` will
   increment by 5, but calling `self._counter("events.dropped", amount=5, source="bus")` will
   also increment by 5 but with `source="bus"` in the label key. The two calls produce different
   counter entries. This is not documented anywhere.

**Severity:** Low (works correctly; fragile design).

---

## 7. UUIDv7Generator

```python
def new_uuid(self) -> uuid.UUID:
    timestamp_ms = time.time_ns() // 1_000_000
    random_a = secrets.randbits(12)
    random_b = secrets.randbits(62)
    value = (
        ((timestamp_ms & ((1 << 48) - 1)) << 80)
        | (0x7 << 76)
        | (random_a << 64)
        | (0b10 << 62)
        | random_b
    )
    return uuid.UUID(int=value)
```

The UUIDv7 layout is correct per RFC 9562:
- Bits 127–80: 48-bit Unix timestamp in milliseconds
- Bits 79–76: version nibble (0x7)
- Bits 75–64: random_a (12 bits)
- Bits 63–62: variant (0b10)
- Bits 61–0: random_b (62 bits)

This is a correct implementation. `secrets.randbits` provides cryptographic randomness.
`time.time_ns() // 1_000_000` gives millisecond precision from a nanosecond source.

One theoretical concern: if two UUIDs are generated within the same millisecond, ordering is
not guaranteed because `random_a` and `random_b` are independently random. RFC 9562 allows a
monotonic counter for sub-millisecond ordering. For Lumora Probe's use as identity generation
(not sort keys), this is acceptable.

**Severity:** Informational.

---

## 8. Path Security

`resolve_capture_path()` validates UUIDv7 format and calls `assert_contained()` which resolves
symlinks before the containment check. This means a symlink inside the capture root that points
outside would be detected. The implementation is correct.

`unpack_capture()` calls `assert_contained()` for every zip member before extracting. This
prevents zip-slip attacks. Symlink entries are explicitly rejected. The implementation is correct.

`pack_capture()` rejects symlinks before packing. Correct.

---

## 9. EventEnvelope Serialization

`to_json_bytes()` uses `model_dump_json()` which goes through Pydantic's JSON encoder.
The `extra="allow"` setting means unknown fields round-trip correctly. The `payload` field is
typed `dict[str, Any]` so nested structures serialize correctly.

One concern: `model_dump_json()` does not produce sorted keys or compact separators. Two
envelopes with the same logical content but different dict insertion order in `payload` will
produce different byte representations. For the `events.jsonl` golden fixture regression tests
that compare byte streams, this matters if payloads are ever constructed from unordered sources.

**Severity:** Low (affects golden fixture stability, not correctness).

---

## 10. Analysis Service

`RuleEngine.evaluate()` validates that findings cite only sequences present in the observed
event set. This is the evidence integrity guarantee:

```python
if not set(finding.cited_sequences).issubset(sequences):
    raise ValueError("finding citations must resolve to observed event sequences")
```

`sequences` is `{event.sequence for event in observed if event.sequence is not None}`. An
event published before the bus assigns a sequence will have `sequence=None` and be excluded
from the valid citation set. This means rules that cite a pre-publication envelope (impossible
in production, but possible in tests using hand-crafted envelopes) would have their citations
silently excluded from validation. The check is correct for the production path.

**Severity:** Informational.
