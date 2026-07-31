# Phase 18 — Production Hardening Completion Report

**Date:** 2026-07-31
**Status:** Complete
**Plan:** `docs/other/phase-18-implementation-plan.md` (Approved; Option B; Search S1;
2,000-instance large study; npm audit report-only)
**Governing phase:** `docs/planning/02-phase-plan.md` §Phase 18
**Implementation tip:** `d2bc0a9`

## Completed work

### Performance (WP-18-01, Option B)

- Measured startup (`lumora serve` → `/api/v1/health/ready`), composition cost,
  2,000-instance study projection browse, 5,000-event bus+governor throughput, ring
  eviction memory cycles, 500-record protocol replay orchestration, and 1/4/8 concurrent
  `/ws/ui` clients with one JSON stream client.
- ADR-0030 capture gates remain green. Unratified dimensions recorded as measured evidence
  in `docs/planning/phase-18-performance-report.md`. F-06 remains OPEN with that evidence
  linked.

### Search prerequisite and virtualization (S1)

- Restored minimal Search over studies/series/instances/events/logs contracts
  (`GET /api/v1/search`) with pagination and kind allowlisting.
- Workspace Search panel uses committed Tabulator assets with remote pagination.
- OpenAPI artifact regenerated.

### Security and accessibility (WP-18-02)

- Boundary/path/secret inventories in `docs/planning/phase-18-security-review.md`.
- Expanded secret-key redaction; path/symlink/plugin containment negatives;
  Search validation coverage.
- Python dependency audit clean; npm findings recorded as build-only exceptions
  (`docs/planning/phase-18-dependency-audit.md`).
- High-contrast theme via runtime `theme` setting; keyboard e2e scenarios added;
  accessibility review written.

### Documentation (WP-18-03)

- Glossary reconciled; F-05 CLOSED.
- Guides: deployment topologies, operator, troubleshooting, user workflows, privacy /
  compliance posture.

## Files added (selected)

- `src/lumora_probe/web/search_routes.py`
- `assets/source/search-panel.js`
- `tests/test_phase18_*.py`
- `docs/guides/{deployment-topologies,operator-guide,troubleshooting,user-workflows,privacy-and-compliance-posture}.md`
- `docs/planning/phase-18-{performance-report,security-review,dependency-audit,accessibility-review,completion-report}.md`

## Acceptance gates

- `uv run ruff check .` / `ruff format --check .`
- `uv run lint-imports --no-cache`
- `uv run basedpyright src/lumora_probe/core src/lumora_probe/shared`
- `uv run pytest -q` (e2e skipped unless `LUMORA_E2E=1`)
- `npm run check:assets`
- Dependency audits documented

## Finding outcomes

| Finding | Outcome |
|---------|---------|
| F-05 | CLOSED |
| F-06 | OPEN — Phase 18 measurement evidence linked; unresolved dimensions not ADR-ratified under Option B |

## Follow-ups

- Optional Option A ADR if startup/large-study/memory/replay/concurrency browser budgets
  should become release gates.
- npm audit CI blocking step remains intentionally deferred.
- Phase 19 packaging / Phase 20 interop remain out of scope.
