# Phase 12 Task Report — T-12-03-02 Explicit Target Configuration

**Date:** 2026-07-29
**Status:** Complete

## Completed work

- Protocol replay requires an explicit `NetworkEndpoint` target at execution time.
- Missing targets are refused before dataset iteration or network activity.
- Replay results retain the resolved target for audit/job composition.

## Verification

- Missing-target acceptance test passes.
- Capture metadata is never used to derive a target.
