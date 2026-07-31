# LifecycleManager Wiring Plan

**Status:** Implemented and verified  
**Target files:** `src/lumora_probe/bootstrap.py`, `src/lumora_probe/web/api.py`,
`tests/test_phase11_capture.py`, `tests/test_bootstrap.py`

---

## Problem

`bootstrap.py` instantiates a fully-built `FastAPI` application but never wires
`LifecycleManager` (`core/lifecycle.py`).  The drain-before-close, bounded timeout, and
`interrupt()`-on-deadline guarantees that exist in `LifecycleManager` are therefore never
exercised in production.  A hard kill (SIGKILL, OOM, supervisor restart) leaves active
captures in `running` state — no `CaptureInterrupted` event, no sealed manifest.

---

## Decided design (do not re-litigate these)

| # | Decision |
|---|----------|
| 1 | `LifecycleManager` is owned and instantiated in `bootstrap.py` (the composition root). |
| 2 | `CaptureEngine` does not satisfy the `Service` protocol directly (its `start()` takes `event_bus=`). Wrap it in a thin `_CaptureEngineAdapter` defined in `bootstrap.py`. |
| 3 | Only `CaptureEngine` is registered with `LifecycleManager`. `EventBus` and `LiveUpdateHub` lack `name`/`health()` and remain in the lifespan's `finally` block unchanged. `ReplayService.startup()` is a one-shot pre-lifecycle call, not a registered service. |
| 4 | `create_app()` gains one new optional parameter: `lifecycle_manager: LifecycleManager | None = None`. When `None`, the existing `capture_engine.start()` / `capture_engine.stop()` path in the lifespan is used unchanged (all existing tests continue to pass). |
| 5 | `LifecycleError` raised by `lifecycle_manager.shutdown()` (deadline exceeded) is caught and logged as a structured warning. Bus and hub cleanup run unconditionally after, whether or not the error was raised. |
| 6 | Adversarial test (drain hangs past grace period → captures get interrupt markers) goes in `test_phase11_capture.py`. A thin structural assertion (manager is on `application.state`) goes in `test_bootstrap.py`. |

---

## Change 1 — `src/lumora_probe/bootstrap.py`

### 1a. Add `_CaptureEngineAdapter`

Insert this class **before** `build_production_app`. It must close over both the engine
and the resolved bus reference so `start()` can forward `event_bus=`.

```python
from lumora_probe.core.lifecycle import LifecycleManager, ServiceHealth


class _CaptureEngineAdapter:
    """Present CaptureEngine as a lifecycle.Service, closing over the event bus."""

    name = "capture-engine"

    def __init__(self, engine: Any, *, event_bus: Any | None) -> None:
        self._engine = engine
        self._bus = event_bus

    async def start(self) -> None:
        await self._engine.start(event_bus=self._bus)

    async def stop(self) -> None:
        await self._engine.stop()

    async def stop_accepting(self) -> None:
        await self._engine.stop_accepting()

    async def drain(self) -> None:
        await self._engine.drain()

    async def flush(self) -> None:
        await self._engine.flush()

    async def interrupt(self, reason: str = "shutdown deadline") -> None:
        await self._engine.interrupt(reason)

    def health(self) -> ServiceHealth:
        return self._engine.health()
```

`Any` is already imported from `typing` in this file.  Import `LifecycleManager` and
`ServiceHealth` from `lumora_probe.core.lifecycle` (add to the existing `core` import block).

### 1b. Update `build_production_app`

After the `bus = EventBus(clock=clock)` line, add:

```python
lifecycle = LifecycleManager(
    shutdown_grace_seconds=config.shutdown_grace_seconds
)
```

After the block that builds `capture_service` / `capture_engine` (search for where
`CaptureEngine` / `CaptureService` is instantiated), add:

```python
_capture_adapter = _CaptureEngineAdapter(
    capture_engine,                          # the CaptureEngine instance
    event_bus=None if bus is None else bus,  # use the production bus
)
lifecycle.register(_capture_adapter)
```

Pass the manager into `create_app()`:

```python
application = create_app(
    ...                            # all existing keyword args unchanged
    lifecycle_manager=lifecycle,
)
```

Store it on `application.state` so tests can inspect it and so Uvicorn's shutdown path
can reference it if needed:

```python
application.state.lifecycle_manager = lifecycle
```

Add this line alongside the existing `application.state.*` assignments at the end of
`build_production_app`.

**Important:** `capture_engine` must still be passed to `create_app()` as `capture_engine=`
— it is used for route wiring (`ring_buffer`, etc.), not just lifecycle.  Do not remove it.

---

## Change 2 — `src/lumora_probe/web/api.py`

### 2a. Add the import

Add `LifecycleManager` to the import from `lumora_probe.core.lifecycle`:

```python
from lumora_probe.core.lifecycle import LifecycleManager
```

Also ensure `LifecycleError` is imported from `lumora_probe.core.errors` (it is already
used elsewhere in this file; confirm it is present).

Add `log_operational` and `get_logger` to the logging import if not already present —
they are used in the warning log below.

### 2b. Add the parameter to `create_app()`

In the `create_app()` signature, add after the last existing parameter:

```python
lifecycle_manager: LifecycleManager | None = None,
```

### 2c. Replace the lifespan body

The current lifespan is (lines ~236–256):

```python
@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncGenerator[None]:
    metrics_lifecycle = cast(Any, metrics_provider)
    if metrics_provider is not None and hasattr(metrics_lifecycle, "attach"):
        await metrics_lifecycle.attach(active_bus)
    if replay_runtime is not None:
        await replay_runtime.startup()
    if capture_engine is not None:
        await capture_engine.start(
            event_bus=None if isinstance(active_bus, NullEventSource) else active_bus
        )
    try:
        yield
    finally:
        if capture_engine is not None:
            await capture_engine.stop()
        if metrics_provider is not None and hasattr(metrics_lifecycle, "detach"):
            await metrics_lifecycle.detach()
        if not isinstance(active_bus, NullEventSource) and hasattr(active_bus, "stop"):
            await cast(Any, active_bus).stop()
        await live_hub.stop()
```

Replace it **in its entirety** with:

```python
@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncGenerator[None]:
    metrics_lifecycle = cast(Any, metrics_provider)
    # Metrics attach always runs first — it has no lifecycle protocol.
    if metrics_provider is not None and hasattr(metrics_lifecycle, "attach"):
        await metrics_lifecycle.attach(active_bus)
    # Replay startup sweep is a one-shot pre-lifecycle call, not a registered service.
    if replay_runtime is not None:
        await replay_runtime.startup()
    # Start the capture engine: managed path or legacy fallback.
    if lifecycle_manager is not None:
        await lifecycle_manager.start()
    elif capture_engine is not None:
        await capture_engine.start(
            event_bus=None if isinstance(active_bus, NullEventSource) else active_bus
        )
    try:
        yield
    finally:
        # Shutdown the capture engine: managed path guarantees drain + interrupt on
        # deadline; legacy fallback preserves existing behaviour for tests.
        if lifecycle_manager is not None:
            try:
                await lifecycle_manager.shutdown()
            except LifecycleError:
                log_operational(
                    get_logger("lumora.lifecycle"),
                    "shutdown grace period exceeded; active captures interrupted",
                    level="warning",
                )
        elif capture_engine is not None:
            await capture_engine.stop()
        # These three always run regardless of which path was taken above.
        if metrics_provider is not None and hasattr(metrics_lifecycle, "detach"):
            await metrics_lifecycle.detach()
        if not isinstance(active_bus, NullEventSource) and hasattr(active_bus, "stop"):
            await cast(Any, active_bus).stop()
        await live_hub.stop()
```

No other changes to `api.py`.  The `create_app()` call in `bootstrap.py` passes
`lifecycle_manager=lifecycle`; every test that calls `create_app()` directly without that
argument gets `None` and takes the legacy branch unchanged.

---

## Change 3 — `tests/test_phase11_capture.py`

### 3a. Adversarial test: drain hangs past grace period

Add this test.  Use the real `EventBus`, a real temporary filesystem, the project's
`StubClock` and `StubIdGenerator` doubles from `tests/doubles/`.

```python
@pytest.mark.asyncio
async def test_lifecycle_shutdown_marks_active_captures_interrupted_on_deadline(
    tmp_path: Path,
) -> None:
    """LifecycleManager.interrupt() seals open captures when the grace period expires."""
    from lumora_probe.core.bus import EventBus
    from lumora_probe.core.lifecycle import LifecycleManager
    from lumora_probe.bootstrap import _CaptureEngineAdapter
    # (import CaptureEngine and its dependencies as done elsewhere in this file)

    clock = StubClock()
    ids = StubIdGenerator()
    bus = EventBus(clock=clock)
    await bus.start()

    engine = CaptureEngine(...)   # match how other tests in this file build it
    capture_id = await engine.start_session(...)   # open one capture

    # Make drain() hang so the grace period will be exceeded.
    original_drain = engine.drain
    async def _hanging_drain() -> None:
        await asyncio.sleep(60)   # far beyond any reasonable grace period
    engine.drain = _hanging_drain  # type: ignore[method-assign]

    adapter = _CaptureEngineAdapter(engine, event_bus=bus)
    lifecycle = LifecycleManager(shutdown_grace_seconds=0.05)   # very short for the test
    lifecycle.register(adapter)
    await lifecycle.start()

    # Restore drain after start so only shutdown drain hangs.
    engine.drain = original_drain

    # Make drain hang again for the shutdown path.
    engine.drain = _hanging_drain  # type: ignore[method-assign]

    from lumora_probe.core.errors import LifecycleError
    with pytest.raises(LifecycleError):
        await lifecycle.shutdown()

    # The manifest must be sealed as INTERRUPTED.
    sealed = engine._sessions.get(capture_id)
    # Session should be gone (interrupt_session pops it) — confirm via the written manifest.
    manifest_path = (
        tmp_path / "captures" / capture_id / "manifest.json"
    )
    import json
    manifest = json.loads(manifest_path.read_text())
    assert manifest["state"] == "interrupted"
    assert manifest["interruption_reason"] is not None

    await bus.stop()
```

**Note to implementer:** match the exact construction pattern for `CaptureEngine` already
used in `test_phase11_capture.py`.  Do not introduce new construction patterns or imports
not already present in that file.  The core assertion is the final three lines; everything
else is setup scaffolding.

---

## Change 4 — `tests/test_bootstrap.py`

### 4a. Structural assertion

Add one test alongside the existing ones:

```python
def test_bootstrap_exposes_lifecycle_manager(tmp_path: Path) -> None:
    """build_production_app must wire a LifecycleManager onto application.state."""
    from lumora_probe.core.lifecycle import LifecycleManager

    application = build_production_app(StartupConfig(data_dir=tmp_path))

    assert hasattr(application.state, "lifecycle_manager")
    assert isinstance(application.state.lifecycle_manager, LifecycleManager)
```

---

## Checklist before marking done

- [x] `import-linter` passes — no new cross-slice imports; `bootstrap.py` already imports
  from `core`.
- [x] `test_phase11_capture.py` adversarial test passes (not skipped).
- [x] `test_bootstrap.py` structural test passes.
- [x] All existing tests in `test_bootstrap.py` and `test_phase11_capture.py` still pass.
- [x] No new dependency added.
- [x] `application.state.lifecycle_manager` is set in `build_production_app`.
- [x] The fallback path in `api.py` lifespan (no `lifecycle_manager`) is exercised by
  existing tests and continues to pass without modification.

---

## What is explicitly out of scope

- Registering `EventBus` or `LiveUpdateHub` with `LifecycleManager` — they lack `name`
  and `health()`.
- Moving `ReplayService` into `LifecycleManager` — `startup()` is a one-shot sweep with
  no corresponding shutdown.
- Changing `CaptureEngine.start()` signature — the `event_bus=` keyword is closed over
  by the adapter.
- Any new ADR — no baseline statement is being deviated from; this wires existing code.
