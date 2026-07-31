# Phase 20 GA Sign-off

**Release:** `lumora-probe` 0.1.0  
**Date:** 2026-07-31  
**Decision:** **APPROVED for trusted engineering deployments**

## Milestone M14 evidence

| Exit criterion | Evidence | Result |
|---|---|---|
| Ratified budgets met or misses documented | Phase 11 budget report; Phase 18 measured evidence and F-06 disposition | PASS WITH ACCEPTED EVIDENCE |
| Keyboard-only operation verified | Phase 18 accessibility e2e suite and review | PASS |
| Glossary reconciled | Phase 18 completion report and glossary updates | PASS |
| No-Node/no-network install | Phase 19 distribution and offline tests | PASS |
| No outbound page-load requests | `tests/test_phase19_no_outbound.py` | PASS |
| Non-root one-volume Docker image | Phase 20 Docker build/run: `uid=10001(lumora)`, readiness `true` | PASS |
| DCMTK/dcm4che/Orthanc interop executed | `docs/planning/phase-20-interop-results.md`, 14 passed | PASS |
| PRD §26 acceptance demonstrated | `docs/planning/phase-20-acceptance-matrix.md` | PASS |
| Definition of Done audited | `docs/planning/phase-20-dod-audit.md` | PASS |
| Known limitations documented | `docs/guides/known-limitations.md` | PASS |

## Release posture

This approval covers the engineering use case: PACS administrators, integration engineers,
developers, QA engineers, healthcare IT teams, and vendor support operating in a trusted,
explicitly configured environment. It does not imply clinical, diagnostic, archival,
anonymization, or Internet-facing security suitability.

Operators must read the known-limitations guide and deployment/operator guides before
exposing the service. In particular, use an authenticated reverse proxy or equivalent
boundary because Lumora Probe has no built-in authentication/RBAC.

## Required retained artifacts

- `CHANGELOG.md`
- `docs/release-notes/v0.1.0.md`
- `docs/planning/phase-20-acceptance-matrix.md`
- `docs/planning/phase-20-dod-audit.md`
- `docs/planning/phase-20-interop-results.md`
- `docs/guides/known-limitations.md`

## Follow-up after sign-off

- Keep scheduled interop enabled and publish future failures rather than hiding them.
- Revisit unratified performance budgets only through a new ADR.
- Expand transfer-syntax coverage only with a reviewed encoder/toolchain and updated matrix.
- Do not infer authentication, PS3.15 conformance, plugin sandboxing, or C-MOVE sub-operation
  visibility from this release.
