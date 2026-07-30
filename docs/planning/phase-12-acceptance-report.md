# Phase 12 Acceptance Report — Replay Engine

**Review date:** 2026-07-30
**Decision:** Accepted after remediation
**Reviewed artifacts:** `phase-12-completion-report.md` and all `phase-12-task-*-report.md` files

## Acceptance basis

Phase 12 implementation and task reports were reviewed against the approved Phase 12 scope,
ADR-0005 replay fidelity tiers, ADR-0007 crash-recovery obligations, ADR-0017 ordering rules,
ADR-0022 golden-test obligations, and the Phase 12 exit criteria in
`docs/planning/02-phase-plan.md`.

The initial review identified four implementation blockers. They were remediated in commit
`d757dd7` and verified by focused component tests:

- `ReplayRuntime` composes protocol replay through the durable job registry, mandatory async audit
  persistence, cooperative cancellation, progress checkpoints, and one shared exclusivity guard.
- `InMemoryJobRegistry.startup_sweep()` and the ASGI lifespan invoke the restart interruption sweep
  for durable and in-memory running jobs.
- The replay runtime owns one application-level exclusivity coordinator and injects it into every
  protocol replay service it creates.
- The golden capture now carries a deterministic `findings.json` set and the regression asserts its
  canonical bytes alongside the replayed event stream, without writing findings into `events.jsonl`.

The original completion report's explicit capture-package input seam and lack of a replay write route
remain documented limitations, not acceptance blockers.

## Quality gates rerun on 2026-07-30

| Gate | Result |
|------|--------|
| `uv run ruff check .` | PASS |
| `uv run ruff format --check .` | PASS |
| `uv run lint-imports --no-cache` | PASS — 7 kept, 0 broken |
| `uv run basedpyright src/lumora_probe/core src/lumora_probe/shared` | PASS — 0 errors |
| `uv run pytest -q` | PASS — 337 passed, 1 skipped |
| `uv build` | PASS — sdist and wheel built |

The opt-in interoperability suite was not run; this remains an explicitly documented limitation.

## Accepted limitations

- Protocol replay input assembly remains an explicit application composition seam.
- Existing SCU transport opens one association per dataset; association-level reconstruction and
  byte-exact/mock-peer replay remain deferred by ADR-0005.
- No replay HTTP write route was added ahead of the approved guardrails.

## Remediation evidence

- `docs/planning/phase-12-remediation-report.md`
- `tests/test_phase12_runtime.py`
- `tests/test_phase12_golden.py`
- `tests/golden/phase12-protocol.lpcap` (`findings.json`)

## Phase transition

Phase 12 is accepted. Phase 13 may begin from its documented entry criterion (Phase 11 exit),
subject to the repository gate that this acceptance report is reviewed and accepted. Phase 13 work
must remain within the approved Viewer work packages and must not implement deferred features.
