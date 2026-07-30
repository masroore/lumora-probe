# ADR-0031: Browser E2E Test Tooling

**Status:** Accepted
**Date:** 2026-07-30

## Context

Phase 13 exit criterion requires: "W/L drag stays within the 100 ms budget with no round trip."
This cannot be honestly asserted without a real browser. Python-only tests (httpx ASGI transport)
cannot observe actual round trips, rendering latency, or DOM interaction timing. The
`docs/planning/07-definition-of-done.md` forbids new dependencies without an ADR.

## Decision

Add Playwright (Python package `pytest-playwright`) as a **dev-only** dependency. Browser e2e
tests run under a new opt-in gate mirroring the interop pattern:

- Tests are marked `e2e` **and** guarded by `LUMORA_E2E=1`.
- They never run in the default gate (`uv run pytest -q`).
- No runtime dependency is added; the shipped package is unaffected.
- No impact on the committed-assets pipeline (ADR-0025).

Local setup: `uv run playwright install chromium` (documented in the test module docstring).

## Consequences

- CI schedules the e2e gate separately: `LUMORA_E2E=1 uv run pytest -m e2e`.
- Local default runs are unchanged.
- Browser tests are inherently slower and environment-sensitive; they are opt-in by design.
- ADR-0030 owns ratified performance budgets; browser tests assert smoke bounds only.
