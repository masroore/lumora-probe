# Maintainability Review

## 1. Coupling Analysis

### 1.1 Good: Dependency injection throughout

Every service that requires a clock, ID generator, or event bus accepts these as constructor
parameters. There are no global singletons outside of `DEFAULT_EVENT_REGISTRY` (which is
intentionally module-level for performance reasons). This makes each component independently
testable and replaceable.

### 1.2 Good: Protocol-based contracts at slice boundaries

`CaptureEventIngress`, `CaptureRepositorySink`, `CaptureClock`, `CaptureIdGenerator` are all
`Protocol` classes defined locally in `captures/service.py`. This means the capture engine
depends on structural interfaces, not concrete types. Swapping the bus implementation requires
no change to the capture engine.

### 1.3 Concern: `bootstrap.py` is a God-object composition root with no lifecycle

`build_production_app()` is a 100-line function that creates every service. With no
`LifecycleManager` and no structured teardown, maintenance of the startup sequence is a manual
discipline. Adding a new service requires remembering to initialize it, wire it, and register
it for health checking — with no compile-time enforcement.

### 1.4 Concern: `CaptureEngine` has 7 constructor parameters

```python
def __init__(
    self,
    captures_root: Path,
    *,
    ring_root: Path | None = None,
    ring_buffer: RingBufferService | None = None,
    event_ingress: CaptureEventIngress | None = None,
    capture_repository: CaptureRepositorySink | None = None,
    clock: CaptureClock,
    id_generator: CaptureIdGenerator,
    fsync_policy: FsyncPolicy = FsyncPolicy.ALWAYS,
)
```

Several of these (`ring_root`, `ring_buffer`) are alternative ways to achieve the same thing.
`ring_buffer` defaults to constructing a `RingBufferService` internally if `None`. This creates
two modes of construction with subtly different semantics. A builder or factory method would
be cleaner.

---

## 2. Cohesion

### 2.1 Good: Single-responsibility modules

`core/clock.py`, `core/ids.py`, `core/errors.py` each have a single clear purpose.
`captures/format.py` owns the capture package format, `captures/service.py` owns lifecycle,
`captures/repository.py` owns the index — clean single-responsibility split.

### 2.2 Concern: `captures/service.py` is 850 lines

`captures/service.py` contains `RingBufferConfig`, `RingBufferRecord`, `RingBufferStatus`,
`RingBufferService`, `CaptureEngine`, and 10+ helper functions. The ring buffer is a separate
concern from the capture engine. It could be split into `captures/ring_buffer.py` without
changing any external interface, improving navigability.

### 2.3 Concern: `associations/network.py` is 960+ lines

`associations/network.py` contains `DICOMListener`, `DICOMSCUClient`, `AssociationAuditRecord`,
`_PDUStats`, `_AssociationState`, and 15+ helper functions. The SCU client and the SCP listener
are distinct concerns that could live in separate files.

---

## 3. Code Duplication

### 3.1 `_identity()` duplicated in `captures/domain.py` and `associations/domain.py`

Both files define a private `_identity()` function with identical logic:

```python
def _identity(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise domain_invariant(f"{field} must be a non-empty string", ...)
    return value
```

This could be extracted to `shared/value_objects.py` or `shared/errors.py` as a utility.

### 3.2 `_canonical_json()` defined in three modules

- `captures/format.py`
- `captures/service.py`
- `captures/repository.py` (via `_canonical_json` local to format)

All have identical implementations:
```python
def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
```

This should be a single utility in `core/` or `shared/`.

### 3.3 `_with_previous()` and `_with_previous_dataset()` in `replay/service.py`

Both are near-identical:

```python
def _with_previous(events):
    previous = None
    for event in events:
        yield previous, event
        previous = event

def _with_previous_dataset(datasets):
    previous = None
    for dataset in datasets:
        yield previous, dataset
        previous = dataset
```

These could be a single generic `_with_previous(items)`.

---

## 4. Error Propagation

### 4.1 Good: Errors are never swallowed silently at domain boundaries

All `except` clauses either re-raise, return a structured result, or record the failure
explicitly. The `# noqa: BLE001` comments are annotated with reasons. There are no bare
`except: pass` patterns.

### 4.2 Concern: `DICOMListener._state_for()` creates a fallback identity

```python
def _state_for(self, association: Any) -> _AssociationState:
    with self._lock:
        state = self._states.get(id(association))
    if state is not None:
        return state
    source_host, source_port = _source_endpoint(association)
    return _AssociationState(
        association_id=self._new_association_id(),
        ...
    )
```

If an event arrives for an association that was not in `_states` (e.g., because `_on_requested`
was missed), a new random ID is generated. Two calls to `_state_for()` for the same association
with no `_states` entry would produce two different IDs, losing the correlation. This is a
defensive fallback but silently breaks association tracking without raising or logging.

### 4.3 Concern: `CaptureEngine.start()` silently ignores bus type errors

```python
async def start(self, *, event_bus: Any | None = None) -> None:
    ...
    if self.event_ingress is None and bus is not None and hasattr(bus, "publish"):
        self.event_ingress = bus
    if bus is not None and hasattr(bus, "subscribe"):
        self._subscription = await bus.subscribe(channel="capture")
```

If `bus` is provided but does not have a `subscribe` method, no subscription is created and no
error is raised. The engine starts "headless" — it will accept sessions but never receive events
from the bus. This silent partial initialization is hard to diagnose.

---

## 5. Readability

### 5.1 `AlertRegistry.snapshot()` threshold comparison is non-obvious

```python
elif value >= critical and critical:
    state = AlertState.CRITICAL
elif value >= warning and warning:
    state = AlertState.WARNING
```

The `and critical` / `and warning` guards check that the threshold is non-zero (preventing
division by zero in a ratio that doesn't exist here) but their intent is not obvious. A comment
would help: `# A threshold of 0 means the alert is disabled`.

### 5.2 `EventBus.publish()` auto-starts the bus

```python
async def publish(self, event, ...) -> EventEnvelope:
    if not self._accepting:
        await self.start()
```

The bus auto-starts on first publish if not already started. This is convenient but can mask
configuration errors where the bus is expected to be started explicitly before publishing. The
auto-start is not documented in the class docstring.

---

## 6. Extensibility

### 6.1 Plugin SDK boundary is clean

Plugins receive `AnalysisContextDTO` and return `FindingDTO` — boundary types defined in
`plugins/contracts.py`. They never see domain aggregates or infrastructure. This is the correct
extensibility model for trusted in-process plugins.

### 6.2 Event registry is open for extension

`EventPayloadRegistry.register()` allows new event schemas to be registered. Plugins and future
slices can add events without modifying the default catalog. The `UnknownEventPayload` fallback
means forward-compatibility is maintained.

### 6.3 `FsyncPolicy` enum supports future durability levels

`FsyncPolicy.ALWAYS`, `FsyncPolicy.FLUSH`, `FsyncPolicy.NEVER` provide a clean extensibility
axis. New policies (e.g., batched fsync) can be added without changing callers.
