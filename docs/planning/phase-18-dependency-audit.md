# Phase 18 Dependency Audit

**Date:** 2026-07-31
**Tools:** `pip-audit 2.10.1`, `npm audit` (npm 11.x), Node ≥22

## Method

```console
uv export --format requirements.txt --all-groups --no-emit-project --output-file audit-requirements.txt
uv run pip-audit --strict -r audit-requirements.txt
npm audit
rm audit-requirements.txt
```

Local reproduction used `pip-audit --disable-pip` after `ensurepip` aborted while creating a
temporary virtualenv in this environment. The audited input matches CI’s locked all-groups
export. CI continues to run the unmodified `pip-audit --strict -r audit-requirements.txt` gate.

## Python (runtime + locked groups)

| Result | Notes |
|--------|-------|
| Clean | `No known vulnerabilities found` |

No reviewed exceptions.

## npm (build-time assets only — report-only in Phase 18)

| Package chain | Severity | Exposure | Mitigation | Owner | Review by |
|---------------|----------|----------|------------|-------|-----------|
| `brace-expansion` via `minimatch` → `glob` → `shelljs` → `@kitware/vtk.js` → `@cornerstonejs/core` | high | Build-time / vendored Cornerstone rendering path only; not a runtime Python dependency; assets are committed | Force-upgrade to `@cornerstonejs/core@5.x` is a breaking change; deferred | frontend assets | 2026-10-31 |
| `js-yaml` via `xmlbuilder2` → `@kitware/vtk.js` → `@cornerstonejs/core` | high | Same as above | Same | frontend assets | 2026-10-31 |

Summary reported by `npm audit`: 8 vulnerabilities (2 moderate, 6 high), all in the
Cornerstone/VTK build graph. **npm remains report-only** for Phase 18 (plan default). A
blocking CI npm audit step is not added.

## Classification

- Runtime Python dependencies: audited clean.
- Dev/tooling Python groups: included in the same export; clean.
- npm packages: build-only per ADR-0025; findings recorded, not CI-blocking.
