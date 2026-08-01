# Lumora Probe 0.1.0 release notes

**Status:** GA implementation and release closure signed off August 1, 2026. Hosted final-SHA
artifacts remain promotion evidence.

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

- Six installed-artifact OS combinations passed in hosted CI run `30716744830` (wheel and sdist on
  Ubuntu, macOS, and Windows) at release-evidence SHA `44edd6e` (source implementation `c445bec`). The run is the release evidence;
  local execution does not replace it.
- The final-SHA pinned-container interoperability artifact records 15 passed, 0 failed in hosted
  CI run `30716744830` (job `91413482214`).
- Reference performance timing passed the ratified p95/rebuild/ring gates on the documented Phase 18
  local host; results remain host-specific and are not claims for network filesystems or every machine.
- No authentication, RBAC, PCAP import, PS3.15 de-identification, or network-filesystem SQLite
  support is added by this closure work.
