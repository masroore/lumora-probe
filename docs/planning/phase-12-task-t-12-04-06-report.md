# Phase 12 Task Report — T-12-04-06 Per-Type Concurrency Bounds

**Date:** 2026-07-29
**Status:** Complete

## Completed work

- Added optional per-job-type concurrency limits to `InMemoryJobRegistry`.
- Limit violations refuse immediately instead of queueing.
- Active counts decrement in the worker `finally` path, including failures and cancellation, so a
  completed slot can be reused.
- Invalid limits are rejected at registry construction.

## Verification

- Limit refusal and slot reuse test passed.
- Existing completion, cancellation, interruption, durable, and progress tests remain passing.
