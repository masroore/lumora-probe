# Phase 20 — Release Completion Report

**Date:** 2026-07-31  
**Status:** Complete; v0.1.0 GA signed off for trusted engineering deployments  
**Governing plan:** `docs/planning/02-phase-plan.md` §Phase 20

## Completed work

### WP-20-01 — Interoperability

- Added real Docker-based DCMTK, dcm4che, and Orthanc suites behind the opt-in scheduled
  gate.
- Covered positive C-ECHO, positive C-STORE, negative calling-AE rejection, and recovery for
  each implementation path.
- Executed a five-case transfer-syntax matrix through the Lumora relay to Orthanc:
  Explicit VR Little Endian, RLE Lossless, JPEG Lossless SV1, JPEG Baseline, and JPEG-LS
  Lossless.
- Published immutable image digests, execution commands, result counts, and failure triage.

### WP-20-02 — Acceptance and ship

- Demonstrated every PRD §26 acceptance item in a traceable matrix.
- Audited Project Charter §11 and the repository Definition of Done.
- Documented C-MOVE, authentication/RBAC, PS3.15, plugin trust, and other limitations where
  operators will encounter them.
- Added v0.1.0 release notes and changelog under the existing package version.
- Built and ran the Docker image as non-root with one volume; readiness returned true.
- Signed off M14 for trusted engineering deployments.

## Files added

- `CHANGELOG.md`
- `docs/guides/known-limitations.md`
- `docs/release-notes/v0.1.0.md`
- `docs/planning/phase-20-acceptance-matrix.md`
- `docs/planning/phase-20-dod-audit.md`
- `docs/planning/phase-20-ga-signoff.md`
- `docs/planning/phase-20-interop-results.md`
- `docs/planning/phase-20-completion-report.md`
- Phase 20 task reports `phase-20-task-t-20-01-01-report.md` through
  `phase-20-task-t-20-01-04-report.md`

## Files modified

- `.github/workflows/ci.yml`
- `CLAUDE.md`
- `docs/guides/operator-guide.md`
- `tests/interop/README.md`
- `tests/interop/docker-compose.yml`

## Verification

| Gate | Result |
|---|---|
| Full default test suite | `496 passed, 17 skipped` |
| Scheduled interoperability suite | `14 passed, 0 failed` |
| Ruff format/lint | Pass |
| Import-linter | 7 contracts kept, 0 broken |
| Basedpyright (`core`, `shared`) | 0 errors, 0 warnings, 0 notes |
| Committed asset check | Pass |
| PRD acceptance matrix | All 10 items PASS |
| Definition-of-Done audit | PASS with documented accepted performance evidence |
| Docker build/run | Pass; non-root `uid=10001(lumora)`, readiness true, one volume |

## Design decisions

- External implementations remain opt-in and scheduled, not part of the fast default gate.
- Release version remains the existing `0.1.0` package version; SemVer policy is documented
  in `CHANGELOG.md`.
- Known limitations are explicit release posture, not hidden roadmap gaps.
- No new ADR or dependency was required in Phase 20.

## Known limitations

See `docs/guides/known-limitations.md` and the published interop triage. The release does not
claim C-MOVE object sub-operation visibility, built-in authentication/RBAC, PS3.15
conformance, plugin sandboxing, or coverage for transfer syntaxes absent from the matrix.

## Implementation commits

- `6e45d20` — DCMTK relay suite
- `e9e7223` — dcm4che relay suite
- `5a52a79` — Orthanc relay suite
- `f4bae7f` — dcm4che health and success assertions
- `bfc49f9` — transfer-syntax matrix
- `290c304` — interoperability result publication
- `195f7b2` — PRD acceptance matrix
- `57de203` — Definition-of-Done audit
- `28c2c92` — known limitations
- `c4925d7` — v0.1.0 release notes/changelog
- `phase-20-ga-signoff` — release sign-off artifact
