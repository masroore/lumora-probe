# Phase 12 Acceptance Report — Replay Engine

**Review date:** 2026-07-30
**Decision:** Accepted
**Reviewed artifacts:** `phase-12-completion-report.md` and all `phase-12-task-*-report.md` files

## Acceptance basis

Phase 12 implementation and task reports were reviewed against the approved Phase 12 scope,
ADR-0005 replay fidelity tiers, ADR-0007 crash-recovery obligations, ADR-0017 ordering rules,
and the Phase 12 exit criteria in `docs/planning/02-phase-plan.md`.

The implementation is accepted because:

- Event replay preserves source sequence semantics while assigning fresh replay identity and
  provenance.
- Protocol replay is explicitly guarded by fidelity, partial-window, dry-run, target, allowlist,
  audit, cancellation, and single-live-replay rules.
- Replay timing is reconstructed from `monotonic_ns`; wall time remains display/audit metadata.
- Job lifecycle, progress, interruption, durable audit, and per-type concurrency behavior are
  covered by tests.
- Replay output is captured through the existing capture seam and has a byte-comparable golden
  regression.
- The replay slice respects slice boundaries and does not import capture or association internals.

## Quality gates rerun on 2026-07-30

| Gate | Result |
|------|--------|
| `uv run ruff check .` | PASS |
| `uv run ruff format --check .` | PASS |
| `uv run lint-imports --no-cache` | PASS — 7 kept, 0 broken |
| `uv run basedpyright src/lumora_probe/core src/lumora_probe/shared` | PASS — 0 errors |
| `uv run pytest -q` | PASS — 334 passed, 1 skipped |
| `uv build` | PASS — sdist and wheel built |

The opt-in interoperability suite was not run; this remains an explicitly documented limitation,
not a Phase 12 acceptance blocker.

## Accepted limitations

- Protocol replay input assembly remains an explicit application composition seam.
- Existing SCU transport opens one association per dataset; association-level reconstruction and
  byte-exact/mock-peer replay remain deferred by ADR-0005.
- No replay HTTP write route was added ahead of the approved guardrails.

## Phase transition

Phase 12 is accepted. Phase 13 may begin from its documented entry criterion (Phase 11 exit);
Phase 13 work must remain within the approved Viewer work packages and must not implement deferred
features.
