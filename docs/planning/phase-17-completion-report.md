# Phase 17 — Observability Completion Report

**Date:** July 31, 2026
**Status:** Complete
**Plan:** `docs/other/phase-17-implementation-plan.md`
**Governing phase:** `docs/planning/02-phase-plan.md` §Phase 17

## Completed work

### Production bootstrap

- Added `build_production_app()` as the production composition root.
- Wired canonical `DataPaths.plugins` discovery into `PluginService`.
- Injected `SystemClock`, diagnostic logging, hook timing, metrics, health, audit, and API
  providers without exposing plugin internals to web routes.
- Added the `lumora serve` command while preserving the explicit non-loopback trust gate.

### Metrics and alerts

- Added `MetricRegistry`, projecting accepted event envelopes from the loop-owned bus.
- Added event name, category, severity, capture, replay, association, diagnostic, and drop
  counters plus plugin invocation/timing/status metrics.
- Kept plugin failure and budget metrics on one counting path: diagnostics own failures and hook
  timing observations own invocations, elapsed time, and budget breaches.
- Added JSON endpoints for all metrics, plugin metrics, and alert facts. Prometheus exposition and
  a Prometheus dependency remain intentionally absent.
- Added configurable warning/critical thresholds with hysteresis and startup validation.
- Added a server-rendered metrics dashboard with current metrics and alerts.

### Health and diagnostics

- Wired per-service probes for event bus, index database, application database, and plugin host.
- Preserved readiness/liveness distinction: a stopped event bus makes the service unready while
  the process remains alive.
- Added plugin health state (`healthy`, `degraded`, `unhealthy`, `disabled`) and version/status
  exposure through the existing plugin API.
- Added incident investigation filters for correlation ID, sequence ranges, and wall-time display
  ranges. Sequence remains the ordering authority.
- Added operational logging guardrails rejecting full event/envelope/payload mirror fields.

### Audit coverage

- Added an append-only `AuditLog` adapter over the existing `app.db.audit_log` table.
- Covered configuration changes, plugin installation, administrative actions, and HTTP security
  failures. Existing capture deletion and replay audit rows remain queryable.
- Documented login, logout, and permission-change categories as deferred until the separate
  authentication/authorization ADR; no fake records are emitted.

## Files added

- `src/lumora_probe/bootstrap.py`
- `src/lumora_probe/core/alerts.py`
- `src/lumora_probe/core/audit.py`
- `src/lumora_probe/core/metrics.py`
- `src/lumora_probe/web/audit_routes.py`
- `src/lumora_probe/web/dashboard_routes.py`
- `src/lumora_probe/web/metric_routes.py`
- `src/lumora_probe/web/templates/metrics_dashboard.html`
- `tests/test_bootstrap.py`
- `tests/test_phase17_observability.py`

## Files modified

- `src/lumora_probe/cli.py`
- `src/lumora_probe/core/config.py`
- `src/lumora_probe/core/logging.py`
- `src/lumora_probe/plugins/contracts.py`
- `src/lumora_probe/plugins/domain.py`
- `src/lumora_probe/plugins/service.py`
- `src/lumora_probe/web/api.py`
- `src/lumora_probe/web/event_routes.py`
- `src/lumora_probe/web/plugin_routes.py`
- `src/lumora_probe/web/security.py`
- `docs/generated/openapi-v1.json`
- `CLAUDE.md`

## Tests added

- Event-to-metric projection and agreement coverage.
- Single counting path for plugin failures.
- Named plugin timing and budget breach coverage.
- Alert threshold and hysteresis coverage.
- Operational log event-mirror rejection.
- Production bootstrap and canonical plugin directory discovery.
- Health, metrics, audit, and dashboard route composition.
- Runtime configuration audit persistence.

## Quality gates

- `uv run pytest -q`: **478 passed, 2 skipped**
- `uv run pytest -q tests/test_phase17_observability.py tests/test_bootstrap.py`: **15 passed**
- `uv run ruff check .`: **passed**
- `uv run ruff format --check .`: **passed**
- `uv run lint-imports --no-cache`: **7/7 contracts kept**
- `uv run basedpyright src/lumora_probe/core src/lumora_probe/shared`: **passed**
- Generated OpenAPI artifact matches `create_app().openapi()`.

## Known limitations

- Authentication, logout, and permission-change audit records remain deferred under the existing
  security ADR; this phase does not invent multi-user semantics.
- Prometheus exposition remains deferred to a future plugin, per ADR-0014.
- Storage utilization and host-level CPU/memory telemetry are not fabricated without an approved
  runtime telemetry contract; current performance indicators are event throughput and measured
  plugin hook timing.

## Follow-up recommendations

- Begin Phase 18 with ratified performance budgets, dependency/security review, accessibility, and
  operator documentation.
- If host/resource telemetry is required, define its source and lifecycle in an ADR before adding
  direct instrumentation paths.
