# Documentation Review

## 1. Architecture Decision Records (ADRs)

The repository contains 32 ADRs in `docs/adr/`. These are the authoritative resolution layer per
CLAUDE.md. The ADRs cover:

- ADR-0001: Baseline document scope
- ADR-0002: Asyncio concurrency model
- ADR-0004: Capture directory structure
- ADR-0006: Domain/boundary model split
- ADR-0007: Single thread boundary
- ADR-0009: No authentication in v1
- ADR-0010: Non-loopback bind acknowledgment
- ADR-0011: Data root layout
- ADR-0012: Package layout
- ADR-0013: Study/Series as projections
- ADR-0015: Pixel decode server-side
- ADR-0016: Client-asserted event quarantine
- ADR-0017: Three-field time model
- ADR-0018: Observed conditions / inferred findings separation
- ADR-0019: Two WebSocket sockets
- ADR-0020: Configuration tiers
- ADR-0021: Plugin trust model
- ADR-0022: Test strategy
- ADR-0023: Background operations / storage authority
- ADR-0025: Committed built assets
- ADR-0026: Redaction / partial de-identification

The ADRs were not individually read during this review, but the CLAUDE.md summary and the code
were used to cross-check compliance. All major ADR decisions verified in the code are implemented
consistently.

**Assessment:** The ADR layer is present, referenced from CLAUDE.md, and demonstrably used as
the authoritative source. This is a significant documentation strength.

---

## 2. Code Comments and Docstrings

### 2.1 Module-level docstrings

Every module reviewed has a concise one-line module docstring:
- `bus.py`: *"Loop-owned event bus with explicit ingress and split subscriber backpressure."*
- `storage.py`: *"SQLite storage primitives and schemas for the rebuildable index and app database."*
- `paths.py`: *"Data-root layout, containment checks, and filesystem safety guards."*
- `captures/service.py`: *"Capture lifecycle, bounded rolling evidence, promotion, and shutdown handling."*

This is consistent and useful. The docstrings describe *what the module does*, not *how it does
it*, which is the right level of abstraction.

### 2.2 Class-level docstrings

Key classes have docstrings that explain their role:
- `EventBus`: *"The asyncio-loop-owned ordering authority for all domain events."*
- `CaptureEngine`: *"Coordinates the bus capture subscriber, explicit sessions, and promotion."*
- `DICOMListener`: *"Threaded pynetdicom SCP with an injected, transport-neutral audit sink..."*
  including the important note about not owning an asyncio loop.
- `LifecycleManager`: *"Own ordered startup, reverse shutdown, and per-service health."*

The docstrings on the architecturally critical classes are particularly good — they name the key
design decision (e.g., "loop-owned ordering authority" is architecturally precise).

### 2.3 Method docstrings

Public methods on key service classes have docstrings explaining their contract. `EventBus.stop()`
says *"Stop ingress after draining all accepted events and close subscriptions."* This matches
the implementation.

Some private helper functions (`_incomplete_aggregates`, `_canonical_json`, etc.) have no
docstrings, which is acceptable for private helpers.

### 2.4 Inline comments

Where used, inline comments explain non-obvious design choices:
- `# noqa: BLE001 - one subscriber must not stop the bus` (in `EventSubscription.deliver`)
- `# noqa: BLE001 - job failures are recorded, not hidden` (in `InMemoryJobRegistry._run`)

These are useful: the noqa suppression is annotated with the reason, not just silenced.

---

## 3. Error Messages

Error messages follow the structured pattern: machine-readable code, human-readable message,
actionable remediation, context. Examples:

```
"[LUMORA-CORE-CONFIG-006] Invalid configuration key 'bind_host' from env.
 Remediation: Correct the value in the named source; startup will not silently default it."
```

```
"[LUMORA-CORE-PATH-005] Invalid capture_id: 'not-a-uuid7'.
 Remediation: Use the UUIDv7 capture identifier returned by the capture API."
```

This is a documentation and UX strength. Operators get actionable guidance without needing to
read source code.

---

## 4. CHANGELOG and Release Notes

`CHANGELOG.md` and `docs/release-notes/v0.1.0.md` are present. These document the v0.1.0 GA
milestone. The release notes include a known limitations section, which is honest and correct.

---

## 5. API Documentation

The OpenAPI schema is auto-generated from FastAPI route definitions. `test_phase08_openapi.py`
exists, suggesting the schema is regression-tested. The event catalog (`EventPayloadRegistry.catalog()`)
generates a versioned JSON catalog of all registered events.

---

## 6. Glossary

`docs/architecture-baseline/19-glossary.md` is referenced in CLAUDE.md with the requirement
that new terms land in the glossary before merge. This is a useful convention for a
DICOM-heavy domain where vocabulary is critical.

---

## 7. Documentation Gaps

| Gap | Severity |
|---|---|
| `associations/service.py` stub has no documentation explaining what it will contain | Low |
| `executor_workers` config has no documentation explaining it is not applied to `asyncio.to_thread` | Medium |
| `bootstrap.py` has no comment explaining that `LifecycleManager` is not yet wired | Medium |
| The difference between `RingBufferService.flush()` (no-op) and `CaptureEngine.flush()` (calls drain) is not documented | Low |
| `_parse_simple_yaml()` documents the YAML subset but not the motivation for not using PyYAML | Low |

---

## 8. Summary

Documentation quality is above average for a single-engineer project at this phase. The ADR
layer is the strongest documentation asset. Module and class docstrings are consistent and
architecturally precise. Error messages are operator-friendly. The main gaps are around missing
explanation for incomplete or non-wired components.
