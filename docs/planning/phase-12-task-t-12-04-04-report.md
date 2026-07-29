# Phase 12 Task Report — T-12-04-04 Progress on the Event Bus

**Date:** 2026-07-29
**Status:** Complete

## Completed work

- Added `JobProgressPublisher`, an injected loop-owned bus contract.
- Job checkpoints publish `ReplayProgressed` envelopes with operation ID, job type, and progress
  payload; no second progress transport was introduced.
- Added `ReplayProgressed` to the normative replay event catalog and regenerated the committed
  catalog artifact.
- Durable checkpoint persistence remains active alongside bus publication.

## Verification

- Job progress publisher test passes and asserts event name, aggregate, and payload.
- Event catalog tests pass.
- Ruff and BasedPyright pass for core/shared changes.

## Known limitations

- Web coalescing and UI-specific rendering consume the normal event stream; no job-specific UI
  route was added in this task.
