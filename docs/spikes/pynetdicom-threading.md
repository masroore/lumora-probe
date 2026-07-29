# pynetdicom threading spike

**Task:** T-03-03-01
**Date:** 2026-07-29
**Status:** Confirmed

## Question

Which thread executes `EVT_C_STORE`, and does the C-STORE caller wait for the handler
before returning?

## Method

`scripts/spikes/pynetdicom_threading.py` starts an in-process pynetdicom SCP on a
loopback port, registers an `EVT_C_STORE` handler, then sends one synthetic Secondary
Capture instance from a separate SCU. The handler records its thread identity and sets a
completion event. The script also records whether the event is set when
`send_c_store()` returns.

## Observation

Run on CPython 3.13 with pynetdicom 3.x on July 29, 2026:

```text
main_thread_name=MainThread
store_thread_name=AcceptorThread@20260729140054
store_thread_differs_from_main=True
handler_completed_before_send_return=True
```

The exact generated thread suffix is runtime-specific. The invariant is that
`EVT_C_STORE` ran on a pynetdicom association/acceptor thread, not the caller's main
thread, and the synchronous `send_c_store()` call returned after the handler completed.

## Engineering consequence

ADR-0002 is confirmed. A future DICOM ingress handler MUST treat the callback as a
blocking-network thread boundary:

- do not access the asyncio event bus directly from the callback;
- enqueue through a thread-safe loop ingress;
- keep callback work bounded and avoid blocking persistence on that thread;
- preserve enough callback context to correlate the event after loop handoff.

No ADR amendment is required. The result constrains T-07-02-03 and Phase 10's DICOM
networking design.

## Reproduction

```console
uv run python scripts/spikes/pynetdicom_threading.py
```
