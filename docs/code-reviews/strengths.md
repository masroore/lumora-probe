# Strengths

This section records components and patterns that are particularly well-designed and worth
preserving in future development.

---

## 1. Event Bus Architecture

The `EventBus` is the strongest component in the codebase. It correctly implements every
requirement from the architecture documents:

- **Gap-free sequencing:** the sequence counter is loop-owned and assigned at publish time,
  making gaps in `events.jsonl` an auditable signal for dropped events.
- **Split backpressure by channel:** `CAPTURE` subscribers have an unbounded queue (never drop);
  `UI` subscribers have a bounded drop-oldest queue with an exact drop count.
- **Single thread boundary:** `publish_from_thread()` uses `run_coroutine_threadsafe` — the
  only crossing between pynetdicom threads and the asyncio loop.
- **Clock anomaly detection:** wall/monotonic divergence is detected automatically and emitted
  as a `ClockAnomalyDetected` event without corrupting the event stream.
- **Budget enforcement:** subscriber execution is timed and a `WarningRaised` diagnostic is
  emitted for budget breaches.
- **Subscriber isolation:** one subscriber failure does not stop the bus from delivering to
  remaining subscribers.

The test suite covers all of these properties with targeted adversarial tests.

---

## 2. Content-Addressed Object Store

`ContentAddressedObjectStore` is a clean, correct implementation:

- SHA-256 content addressing prevents duplicate storage and enables integrity verification.
- Atomic write-then-rename with `os.fsync` prevents partial objects from appearing.
- Deduplication is free: `if destination.is_file(): return digest`.
- The `verify()` method re-computes the digest at read time, enabling integrity checks.
- `path_for()` validates the digest format and calls `assert_contained()` before constructing
  the path — no path traversal possible.

---

## 3. Structured Error Hierarchy

The `LumoraError` hierarchy provides:

- Machine-readable `code` (e.g., `LUMORA-CORE-PATH-004`)
- Human-readable `message`
- Actionable `remediation`
- Structured `context` dict

Every error subclass maps to a specific concern (`ConfigurationError`, `PathSecurityError`,
`NetworkFilesystemError`, `VersionMismatchError`). The `as_dict()` method makes errors directly
serializable to API responses. The `__str__` representation is useful in logs.

This is significantly better than the typical ad-hoc exception hierarchy.

---

## 4. Capture Package Format

The capture package design is excellent:

- A capture is a **directory, not a blob** — individual files (`manifest.json`, `events.jsonl`,
  `pdus.jsonl`, `objects/`) are independently readable and repairable.
- The manifest uses Pydantic v2 with `extra="allow"` — forward-compatible with future fields.
- Object storage is content-addressed by SHA-256 — deduplication and integrity checking for free.
- `.lpcap` is the directory zipped — trivially portable.
- The `CapturePackageWriter` uses atomic manifest writes (write-then-rename with fsync).
- `FsyncPolicy` supports three durability levels without changing callers.

---

## 5. Value Object Implementation

Value objects (`AETitle`, `DICOMUID`, `NetworkEndpoint`, `PresentationContext`) are:

- `@dataclass(frozen=True, slots=True)` — immutable, memory-efficient, hashable.
- Framework-free — no Pydantic, no FastAPI dependencies.
- Invariant-enforced in `__post_init__` using the structured `domain_invariant()` helper.
- Complete — cover all the DICOM identity types needed by the domain layer.

The `type(self.field) is not int` pattern (instead of `isinstance`) is intentional to reject
`bool` values (which are `isinstance(True, int)`). This is the correct idiomatic Python guard
for strict type checking.

---

## 6. Clock and Identity Injection

The `Clock` and `IdGenerator` protocols are injected everywhere they are needed. `time.monotonic_ns()`
and `uuid.uuid4()` are banned outside `core/` by import-linter enforcement. This means:

- Tests never call `time.sleep()` to wait for timing effects.
- Deterministic UUIDv7 sequences are available via `SeededUUIDv7Generator`.
- All temporal ordering is testable.

This is a disciplined application of the design principle; many codebases pay lip service to
injectable clocks but then import `datetime.now()` in domain code.

---

## 7. Three-Field Time Model (ADR-0017)

The implementation correctly separates:

- `occurred_at` — wall clock UTC, for display only.
- `monotonic_ns` — monotonic counter, for duration and ordering.
- `sequence` — per-capture gap-free integer, for audit and replay.

Each field has exactly one purpose and they are never used interchangeably. The `ClockAnomalyDetected`
event fires when wall and monotonic diverge beyond a threshold, rather than corrupting either
value. This is the correct approach for an observability tool where temporal integrity is paramount.

---

## 8. Path Security Model

The path security model is layered and consistent:

1. `is_uuid7()` validates that capture IDs are structurally valid before constructing paths.
2. `assert_contained()` resolves symlinks and checks containment.
3. `resolve_capture_path()` combines both.
4. `unpack_capture()` applies `assert_contained()` to every zip member.
5. `ContentAddressedObjectStore.path_for()` validates digest format and calls `assert_contained`.

Every path that originates from user input passes through at least one of these guards.

---

## 9. LifecycleManager Design

`LifecycleManager` is a clean implementation of the ordered-startup/reverse-shutdown pattern:

- Services register in dependency order; shutdown runs in reverse.
- `stop_accepting()`, `drain()`, and `flush()` are called before `stop()` if present.
- A bounded grace period (`asyncio.timeout()`) prevents shutdown hangs.
- Timeout causes `interrupt()` to be called, which records `CaptureInterrupted`.
- Health checking aggregates per-service readiness/liveness.

The design is correct and production-grade. It is a shame it is not wired to the production
composition root.

---

## 10. Plugin SDK Boundary

The plugin SDK boundary is clean:

- Plugins receive `AnalysisContextDTO` (events as data) and return `FindingDTO` (findings as data).
- Plugins never see `EventEnvelope` (the internal domain type), `EventBus`, repositories,
  or any infrastructure object.
- `RuleEngine.evaluate_plugin()` applies the same evidence validation (citation resolution)
  to plugin findings as to bundled rules.
- `ADR-0021` honestly acknowledges that in-process plugins cannot be sandboxed; the manifest
  is disclosure, not enforcement.

---

## 11. Audit Log Design

`AuditCategory` covers the right categories for a v0.1.0 tool:
`ConfigurationChanged`, `AdministrativeAction`, `SecurityFailure`, `PluginInstalled`.

The `AUDIT_CATEGORY_COVERAGE` mapping explicitly documents which categories are deferred
(Login/Logout/PermissionChange pending auth ADR) and why. This is honest and avoids creating
fake audit records.

---

## 12. Alert Hysteresis

`AlertRegistry` implements hysteresis correctly:

```python
if previous is AlertState.CRITICAL and value >= critical * hysteresis_ratio:
    state = AlertState.CRITICAL
elif previous is AlertState.WARNING and value >= warning * hysteresis_ratio:
    state = AlertState.WARNING
```

Alerts do not flap between states on the threshold boundary. A critical alert remains critical
until value drops below `critical * 0.8`. This is the correct operational behavior for
threshold-based alerting.
