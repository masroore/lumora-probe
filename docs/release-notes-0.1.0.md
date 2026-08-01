# Lumora Probe 0.1.0 release notes

**Status:** GA implementation signed off July 31, 2026; release-closure verification updated
August 1, 2026. Hosted final-SHA artifacts remain promotion evidence.

## Verified closure work

- Production composition exposes a narrow `ProductionRuntime` handle without changing the
  `build_production_app()` entry point.
- DICOM callback ingress is bounded and reports saturation, timeout, completion, persistence, and
  late-callback outcomes. C-STORE failure statuses are explicit.
- Capture session ownership refuses late callbacks and seals interrupted work idempotently.
- Collection pagination, projection rebuild, and segmented ring persistence use the ratified
  direct-`sqlite3` storage seam (ADR-0035).
- Structural release-closure tests cover ring turnover, DICOM saturation/recovery, graceful active
  traffic on POSIX, and forced lifecycle deadlines.
- The canonical BasedPyright, Ruff, import-linter, full pytest, and exported-lock `pip-audit` gates pass locally.
- Wheel and sdist installed smoke pass locally from outside the source checkout.

## Evidence still environment-specific

- Six installed-artifact OS combinations are gated by CI; local execution does not replace their
  hosted artifacts.
- The retained pinned-container interoperability artifact records 14 passed, 0 failed on July 31,
  2026; the final-SHA scheduled CI artifact remains pending.
- Reference performance timing is limited to the Phase 18 local host; unresolved p95 budgets remain
  named in `docs/planning/phase-18-performance-report.md`.
- No authentication, RBAC, PCAP import, PS3.15 de-identification, or network-filesystem SQLite
  support is added by this closure work.
