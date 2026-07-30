# Phase 12 Acceptance Report — Replay Engine

**Review date:** 2026-07-30
**Decision:** Blocked pending remediation
**Reviewed artifacts:** `phase-12-completion-report.md` and all `phase-12-task-*-report.md` files

## Acceptance basis

Phase 12 implementation and task reports were reviewed against the approved Phase 12 scope,
ADR-0005 replay fidelity tiers, ADR-0007 crash-recovery obligations, ADR-0017 ordering rules,
ADR-0022 golden-test obligations, and the Phase 12 exit criteria in
`docs/planning/02-phase-plan.md`.

The implementation passes its isolated service and quality-gate tests, but acceptance is blocked
by production-composition gaps:

- Replay services are not wired into an application composition path with a durable job record and
  mandatory audit sink.
- Startup does not invoke the durable interruption sweep, so running jobs are not proven to become
  `interrupted` after restart.
- Live-replay exclusivity defaults to a per-service coordinator rather than a shared application
  coordinator.
- The golden regression compares only replayed event bytes; it does not compare a byte-stable
  finding set as required by ADR-0022.

These are implementation blockers, not accepted limitations. Phase 13 remains blocked until they
are remediated and the quality gates are rerun.

## Quality gates rerun on 2026-07-30

| Gate | Result |
|------|--------|
| `uv run ruff check .` | PASS |
| `uv run ruff format --check .` | PASS |
| `uv run lint-imports --no-cache` | PASS — 7 kept, 0 broken |
| `uv run basedpyright src/lumora_probe/core src/lumora_probe/shared` | PASS — 0 errors |
| `uv run pytest -q` | PASS — 334 passed, 1 skipped |
| `uv build` | PASS — sdist and wheel built |

The opt-in interoperability suite was not run; this remains an explicitly documented limitation.

## Accepted limitations

- Protocol replay input assembly remains an explicit application composition seam.
- Existing SCU transport opens one association per dataset; association-level reconstruction and
  byte-exact/mock-peer replay remain deferred by ADR-0005.
- No replay HTTP write route was added ahead of the approved guardrails.

## Blocking findings

1. Add an application-level replay composition adapter that creates durable operation records,
   supplies the mandatory audit sink, and wires replay cancellation/progress to the job registry.
2. Invoke the durable interruption sweep from application startup and share one replay exclusivity
   coordinator across all live replay services.
3. Extend the golden fixture/test to compare a deterministic finding-set artifact as well as the
   event stream.

## Phase transition

Phase 12 is **not accepted**. Phase 13 must not begin until the blocking findings are closed and
this report is updated with a passing acceptance decision.
