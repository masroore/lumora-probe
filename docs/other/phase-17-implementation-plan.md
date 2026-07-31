# Phase 17 — Observability: Implementation Plan

**Date:** 2026-07-31
**Status:** Implemented — completion report: `docs/planning/phase-17-completion-report.md`
**Predecessor:** Phase 16 (Plugin SDK) — complete
**Milestone:** M13 — Release Candidate (`04-milestones.md`)
**Governing docs:** `02-phase-plan.md` §Phase 17, `01-work-breakdown-structure.md` C-17,
`06-deliverables.md` §Phase 17, `14-observability-architecture.md`,
`12-security-architecture.md` §10, ADR-0012, ADR-0014, ADR-0021, ADR-0022

---

## Corrections applied in this revision

Compared to the prior draft and verified against the tree as of Phase 16 exit:

| Prior claim | Reality |
|---|---|
| 8 import-linter contracts | **7** contracts in `.importlinter` |
| New `observability/` slice | **Conflicts ADR-0012** package list and WBS module column (`core` / `web` / `plugins`). Prefer extending `core` + `web` |
| Invent `HealthReporter` / new health routes | **`core/health.py`** (`HealthRegistry`, `HealthReport`), **`core/lifecycle.Service.health()`**, **`web/health_routes.py`** already exist with ready/live endpoints |
| Invent new `audit_log` schema | Table already in `core/storage.py` `_APP_SCHEMA`; writers exist for capture delete + replay audit |
| Bootstrap blocks *all* Phase 17 | Bootstrap required for **plugin** observability only; metrics/health/logging/audit can use test composition |
| `DiagnosticSink` at `contracts.py:15` | Line 15 is `EventDTO` decorator; **`DiagnosticSink` at line 132** |
| Config via `settings.toml` | **`lumora.toml` / `.lumora.toml` / `LUMORA_*`** (`StartupConfig`) |
| Create `web/health_routes.py` | File already exists — extend provider wiring, do not recreate |
| Phase 16 follow-up path `config.data_dir / "plugins"` | Prefer canonical **`DataPaths.plugins`** (`root / "plugins"`) |

---

## 0. Pre-phase gate: production bootstrap (plugin path)

Phase 16 follow-up (`docs/planning/phase-16-completion-report.md`):

> Wire `PluginService(PluginRepository(...), clock=core_clock)` into the production
> application bootstrap before Phase 17's **per-plugin** observability work.

**Scope of the gate:** required before **T-17-02-02** (and any live plugin metrics that
need a real `PluginService`). Not a hard block on T-17-01-01, T-17-02-01, T-17-02-03,
or T-17-02-06 — those can advance with existing test-time composition of `create_app()`.

### 0.1 Current state (verified)

| Component | Location | Status |
|---|---|---|
| `PluginService` | `plugins/service.py` | Complete. `repository`, optional `clock`, `diagnostic_sink` |
| `PluginRepository` | `plugins/repository.py` | Filesystem discovery from plugins root |
| `PluginProvider` | `web/plugin_routes.py` | Mapping protocol: `records` / `inspect` / `set_enabled` |
| `EmptyPluginProvider` | `web/plugin_routes.py` | Default when no provider injected |
| `create_app()` | `web/api.py` | Multi-provider composition; accepts `plugin_provider`, `health_provider`, `event_bus`, stores, runtimes, … |
| Module `app = create_app()` | `web/api.py` | ASGI convenience target with **defaults only** |
| `StartupConfig` | `core/config.py` | Required `data_dir`; env prefix `LUMORA_`; files `lumora.toml` / `.lumora.toml` |
| `DataPaths` | `core/paths.py` | `plugins`, `app_db`, `index_db`; `create_directories()` + `initialise()` |
| `SystemClock` / `UUIDv7Generator` | `core/clock.py`, `core/ids.py` | Production clock + IDs |
| `MonotonicClock` | `plugins/service.py` | Structural protocol: `monotonic_ns()` only; `SystemClock` satisfies |
| `DiagnosticSink` | `plugins/contracts.py` | Callback for `PluginDiagnostic`; not production-wired |
| CLI plugin install | `cli.py` | Uses `PluginRepository` + `--data-dir`; offline of app bootstrap |
| `HealthRegistry` | `core/health.py` | Aggregate ready/alive + per-service `ServiceHealth` |
| Health HTTP | `web/health_routes.py` | `GET /api/v1/health`, `/live`, `/ready` |
| Event bus | `core/bus.py` | Loop-owned; subscribe / publish / publish_from_thread |
| Structured logging | `core/logging.py` | structlog + correlation context + redaction |
| `audit_log` table | `core/storage.py` | Exists; used by studies cascade + operations replay audit |
| Entry script | `pyproject.toml` | `lumora = lumora_probe.cli:main` (client/offline; no `serve` yet) |

### 0.2 Protocol mismatch: `PluginService` vs `PluginProvider`

`PluginService` returns `PluginRecord`; `PluginProvider` expects `Mapping[str, Any]`.
`PluginRecord.as_dict()` produces the API shape.

**Option A — adapter in composition root (recommended):**

```python
class PluginServiceAdapter:
    """Adapts PluginService domain returns to the PluginProvider mapping protocol."""

    def __init__(self, service: PluginService) -> None:
        self._service = service

    def records(self) -> Sequence[Mapping[str, Any]]:
        return tuple(record.as_dict() for record in self._service.records())

    def inspect(self, plugin_id: str) -> Mapping[str, Any]:
        return self._service.inspect(plugin_id).as_dict()

    def set_enabled(self, plugin_id: str, enabled: bool) -> Mapping[str, Any]:
        return self._service.set_enabled(plugin_id, enabled).as_dict()
```

**Must not live in `web/`:** `plugin_boundary` forbids `lumora_probe.web` from importing
`lumora_probe.plugins.service`. Composition root is outside all slice source lists.

**Option B — change `PluginService` to return mappings:** pollutes domain service with
web shapes; breaks Phase 16 tests that assert `PluginRecord`. **Rejected.**

### 0.3 Bootstrap composition design

No production bootstrap module today. Resolution: add
`src/lumora_probe/bootstrap.py` (composition root).

```python
def build_production_app(config: StartupConfig) -> FastAPI:
    paths = DataPaths.from_config(config)
    paths.initialise()
    clock = SystemClock()
    id_gen = UUIDv7Generator()
    storage = StorageDatabases.from_paths(paths)
    storage.initialise()

    bus = EventBus(clock=clock, id_generator=id_gen)  # match EventBus ctor
    health = HealthRegistry()
    # register service probes as runtimes come online…

    plugin_repo = PluginRepository(paths.plugins)
    plugin_service = PluginService(
        plugin_repo,
        clock=clock,
        diagnostic_sink=_publish_plugin_diagnostic,  # §0.4
    )
    plugin_provider = PluginServiceAdapter(plugin_service)

    # HealthRegistry.check() -> HealthReport; HealthProvider needs Mapping.
    # Thin adapter: return (await registry.check()).as_dict()
    health_provider = HealthRegistryAdapter(health)

    return create_app(
        plugin_provider=plugin_provider,
        health_provider=health_provider,
        event_bus=bus,  # EventBus exposes subscribe/ui_queue_size; confirm LiveEventSource fit
        # wire remaining stores/runtimes as production paths already do in tests
    )
```

**Import-linter:** 7 contracts govern listed slices. Root-level `bootstrap.py` is not a
`source_modules` entry → permissible without new contracts. Verify with
`uv run lint-imports --no-cache`.

**Do not invent an `observability/` package** without a new ADR amending ADR-0012.
WBS places metric registry, health, logging discipline, alerting, audit under **`core`**;
API/dashboard under **`web`**; per-plugin health under **`plugins`**.

### 0.4 Diagnostic sink wiring

`PluginService` emits `PluginDiagnostic` (`event_name`: `"ErrorRaised"` | `"WarningRaised"`,
plus `plugin_id`, `hook`, `message`, optional timing fields) via `diagnostic_sink`.

For ADR-0014 one counting path, production sink should feed the metric registry and/or
bus. Choices (resolve in T-17-01-01 / T-17-02-02):

1. **Domain events in catalog** (`PluginErrorRaised` / `PluginWarningRaised`) — strongest
   alignment with “metrics from stream”; requires catalog regen.
2. **Internal metric observer** registered as sink + optional structlog — smaller surface;
   plugin counters not pure stream projections unless also mirrored to bus.

Interim: structured log sink OK if metric path records the same diagnostic payload.

### 0.5 Entry point

CLI today: health/captures/plugins client + offline inspect. No server runner.

Options (pick one in implementation):

- `lumora serve` subcommand → `build_production_app` + uvicorn
- `python -m lumora_probe` via `__main__.py`

Update `pyproject.toml` only if a new console script is required; existing script is
`lumora`.

### 0.6 Bootstrap tests

| Test | Type | Asserts |
|---|---|---|
| `test_bootstrap_wires_plugin_service_with_clock` | component | Injected clock; non-zero `last_elapsed_ns` after timed hook |
| `test_bootstrap_plugin_provider_returns_dicts` | component | `GET /api/v1/plugins` non-empty when plugins dir populated |
| `test_bootstrap_creates_plugin_directory` | component | `DataPaths.initialise()` creates `plugins/` |
| `test_bootstrap_diagnostic_sink_receives_failures` | component | Hook failure → sink/bus/metric path |
| `test_empty_plugin_dir_returns_empty_list` | unit | Graceful empty discovery |

### 0.7 Gate acceptance

- [ ] `PluginService(PluginRepository(paths.plugins), clock=SystemClock(), …)`
- [ ] Adapter wired as `plugin_provider` into `create_app`
- [ ] Live `GET /api/v1/plugins` not stuck on `EmptyPluginProvider`
- [ ] Hook budgets active when clock injected
- [ ] Diagnostic sink wired (log and/or bus/metrics)
- [ ] `lint-imports` 7/7; basedpyright core+shared clean; full suite green

---

## 1. Phase 17 scope summary

**Objective:** One counting path — metrics cannot disagree with events (ADR-0014).

### Work packages (WBS C-17)

| WP | Name | Tasks | WBS modules |
|---|---|---|---|
| WP-17-01 | Metrics from events | T-17-01-01 … T-17-01-04 | core, web, tests |
| WP-17-02 | Health and diagnostics | T-17-02-01 … T-17-02-06 | core, plugins, web |

### Exit criteria (`02-phase-plan.md`)

1. Metric + underlying event count agree **by construction**
2. “Tool got slow” → named plugin
3. Health distinguishes readiness vs liveness **per service**
4. `app.log` contains no domain event mirror
5. Prometheus exposition remains absent (plugin later; no core dep)

### Discharges

- ADR-0014 (metrics from stream; operational log ≠ event mirror)
- ADR-0021 (per-plugin health, metrics, version)

### Deliverables (`06-deliverables.md`)

Event-derived metric registry + API · per-service and per-plugin health · audit log
coverage for `12` §10 · alerting thresholds · incident investigation support · metrics
dashboard · agreement suite + `app.log` discipline suite

---

## 2. WP-17-01 — Metrics from events

### T-17-01-01: Event-derived metric registry

**WBS:** deps `T-07-02-01`, module `core`, P0

**What:** In-process registry that **projects** the bus stream into counters/gauges/
histograms. No parallel instrumentation API for domain activity (ADR-0014).

**Design constraints:**

- Subscribe on loop-owned bus (`core/bus.py`); updates non-blocking
- Categories from `14` §6: API activity, DICOM associations, event throughput, capture
  activity, replay activity, plugin health, storage utilization, performance indicators
- No `prometheus_client` (or any Prometheus exposition library) in core deps
- Plugin metrics: from diagnostic path + optional hook timing on `PluginRecord` (timing
  already measured in `PluginService` when clock injected)
- Inject `Clock` if wall time needed; no `time`/`uuid` imports outside `core`

**Suggested placement (align WBS + ADR-0012):**

```
src/lumora_probe/core/metrics.py   # MetricKind, MetricValue, MetricRegistry
```

Public re-export via `core/contracts.py` or `core/api.py` only if other slices need it.
Web must not import registry internals if a contracts surface is introduced for slices;
composition root may wire freely.

**Key types (illustrative):**

```python
class MetricKind(StrEnum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass(frozen=True, slots=True)
class MetricValue:
    name: str
    value: float
    labels: tuple[tuple[str, str], ...]
    kind: MetricKind


class MetricRegistry:
    def observe(self, event: EventEnvelope) -> None: ...
    def snapshot(self) -> tuple[MetricValue, ...]: ...
```

**Plugin metric names (illustrative, `14` §15):**

- `plugin.hook.invocations` (counter; plugin_id, hook)
- `plugin.hook.elapsed_ns` (histogram; plugin_id, hook)
- `plugin.hook.errors` (counter; plugin_id, hook)
- `plugin.hook.budget_breaches` (counter; plugin_id)
- `plugin.status` (gauge; plugin_id, status)
- `plugin.auto_disables` (counter; plugin_id)

### T-17-01-02: Metric exposure on API

**WBS:** deps T-17-01-01, T-08-01-01; module `web`; P0

**Routes (suggested):**

- `GET /api/v1/metrics` — full snapshot
- `GET /api/v1/metrics/plugins` — plugin-scoped
- Optional category filter

JSON only. No Prometheus text format in core. New router e.g.
`web/metric_routes.py`; register in `create_app` via injected provider protocol (same
pattern as health/plugins).

### T-17-01-03: Metrics dashboard

**WBS:** deps T-17-01-02, T-13-04-07; module `web`; P1

**What:** Operational dashboard per `14` §16: system overview, DICOM activity, event
processing, storage, API health, plugin status, recent alerts.

**Design:** Jinja2 + htmx (existing workspace pattern). Prefer server-rendered partials
polling metrics API / live hub. New frontend charting library only if justified; if
added, vendored assets + ADR-0025 provenance + `npm run check:assets`. Default: no new
JS chart dependency for MVP.

### T-17-01-04: Metric/event agreement test

**WBS:** deps T-17-01-01; module `tests`; P0

**What:** Prove agreement **by construction**.

1. Publish N known envelopes through bus
2. Assert registry counters equal N for those types
3. Assert registry has no independent write path for domain counters
4. Property: for each projected event type, metric count == observed event count

---

## 3. WP-17-02 — Health and diagnostics

### T-17-02-01: Per-service health reporting

**WBS:** deps T-04-03-06; module `core`; P0

**What:** Every runtime `Service` reports health; aggregate ready vs alive (`14` §9).

**Build on existing code — do not redesign:**

| Existing | Role |
|---|---|
| `core/lifecycle.Service.health() -> ServiceHealth` | Per-service contract |
| `core/lifecycle.ServiceHealth` | `name`, `ready`, `alive`, `detail` |
| `core/health.HealthRegistry` | Register probes; aggregate `HealthReport` |
| `core/health.HealthReport.as_dict()` | API shape with `services[]` |
| `web/health_routes.py` | `/health`, `/live`, `/ready` |
| `InMemoryHealthProvider` | Default empty `services: []` |

**Work:** register real probes (capture engine, event bus, SQLite stores, plugin host,
replay runtime, …) in bootstrap/lifecycle; adapt `HealthRegistry` to `HealthProvider`
(`check()` → `HealthReport.as_dict()`, not the report object itself). Fill `services` so
readiness can fail while liveness holds (already tested pattern in
`tests/test_phase08_settings_health_api.py`).

### T-17-02-02: Per-plugin health and version

**WBS:** deps T-16-02-05; module `plugins`; P0  
**Also needs:** §0 bootstrap gate

**What:** “Tool got slow” → named plugin (`14` §15, ADR-0021).

**Design:**

- Inspect payload already includes `version`, `status`, `failure_count`,
  `last_elapsed_ns`, `last_error` via `PluginRecord.as_dict()`
- Extend inspect/list (or metrics side channel) with health rollup:
  - degraded: `failure_count > 0` and still enabled/loaded
  - unhealthy: `status == PluginStatus.FAILED` (`"failed"`)
- Plugin host probe contributes to `HealthRegistry`
- Hook timing metrics from T-17-01-01 complete the “named plugin” story

### T-17-02-03: Operational logging discipline

**WBS:** deps T-04-03-02; module `core`; P0

**What:** `app.log` is operational logging, **not** a domain-event mirror (ADR-0014).

**Build on:** `core/logging.py` — structlog setup, redaction, `correlation_context`,
`new_correlation_id`.

**Work:**

- Audit call sites for event-payload mirroring into logs
- Guidelines: lifecycle, errors, config, security; not full envelope dumps
- Test and/or lint for anti-patterns
- Correlation shared with events where applicable (`14` §8). Prefer injectable IDs for
  new code; existing `new_correlation_id` uses stdlib `uuid` **inside core** (allowed)

### T-17-02-04: Alerting thresholds

**WBS:** deps T-17-01-01; module `core`; P1

**What:** Configurable thresholds (`14` §11).

**Design:**

- Config via `StartupConfig` extension and/or `lumora.toml` — **not** `settings.toml`
- Defaults: plugin error rate, budget breaches, event drop/throughput, storage
- State: OK → WARNING → CRITICAL with hysteresis
- Surface via API + dashboard; external notify = plugin later
- Prefer alert facts also visible on the event/metric path (no silent side channel)

### T-17-02-05: Incident investigation support

**WBS:** deps T-17-01-01, T-13-04-04; module `web`; P1

**What:** Timeline reconstruction, correlation, evidence preservation (`14` §17).

**Existing substrate:**

- Envelopes: `sequence`, `monotonic_ns`, `occurred_at` (ADR-0017)
- Event list API with query/pagination (`web/event_routes.py`)
- Capture packages / handover for evidence

**Work:** time/sequence range investigation UX or API polish; correlation ID tracing;
document operator path. Avoid re-implementing capture export.

### T-17-02-06: Audit log coverage

**WBS:** deps T-06-01-02; module `core`; P0

**What:** Audit log in `app.db` covering **`12` §10** categories.

#### Authoritative category list (`12-security-architecture.md` §10)

- Login
- Logout
- Permission changes
- Configuration changes
- Plugin installation
- Administrative actions
- Security failures

Records should be tamper-evident where practical (append-only table already).

#### Existing schema (do not replace)

```sql
-- core/storage.py _APP_SCHEMA
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
```

**Existing writers:**

- `CaptureDeleted` — `studies/repository.py` cascade
- `ProtocolReplayAudit` — `core/operations.py` (`append_replay_audit`)

#### WBS paraphrase vs baseline

WBS acceptance text says: “associations, config changes, replays, exports, deletions”.
That is a **product paraphrase**, not a copy of `12` §10. Implementation plan:

| `12` §10 category | Phase 17 stance |
|---|---|
| Login / Logout / Permission changes | **No multi-user auth yet** (deferred ADR). Record explicit N/A + single-operator admin actions as `Administrative actions` where applicable; do not fake login events |
| Configuration changes | Settings mutations, bind/exposure gates |
| Plugin installation | CLI install path (+ enable/disable as administrative) |
| Administrative actions | Deletes, exports, enable/disable, retention ops, etc. |
| Security failures | Exposure refusal, path containment failures, authz denials if any |

Map WBS examples onto these categories (replay → administrative/security-relevant ops
already partially covered; deletions → `CaptureDeleted`; exports → new audit rows).

**Work:** shared append helper (if missing), query API as needed, tests that required
categories produce rows; schema migration only if columns proven necessary (prefer
`payload_json` over table rewrite).

---

## 4. Dependency graph

```
§0 Bootstrap (plugin composition)
  └── T-17-02-02 (plugin health) ← also needs metrics/timing from T-17-01-01

Event bus (exists; T-07-02-01 done)
  └── T-17-01-01 metric registry
        ├── T-17-01-02 API
        │     └── T-17-01-03 dashboard
        ├── T-17-01-04 agreement test
        ├── T-17-02-04 alerting
        └── T-17-02-05 incident investigation (also event routes / T-13-04-04)

Independent / early-parallel:
  T-17-02-01 service health (HealthRegistry wiring)
  T-17-02-03 logging discipline
  T-17-02-06 audit coverage (app.db already exists)
```

**Parallel:** T-17-02-01, T-17-02-03, T-17-02-06 alongside T-17-01-01.  
**Sequential:** T-17-01-02/03/04 after T-17-01-01; T-17-02-02 after §0 + registry/timing.

---

## 5. Architecture constraints checklist

| Constraint | Source | Applies to |
|---|---|---|
| `time`/`uuid` only in `core/` | ADR-0022 | All non-core modules |
| Slices import only other slices’ `contracts.py` | `.importlinter` (7 contracts) | Any new module under a slice |
| No new top-level package without ADR | ADR-0012 | Reject default `observability/` slice |
| No `domain.py` fastapi/sqlalchemy/jinja2 | ADR-0006 / domain_purity | Keep domain pure if added |
| SQLAlchemy Core only if used; prefer existing sqlite3 helpers | ADR-0006 / `core/storage.py` | Audit writes |
| Metrics from events | ADR-0014 | T-17-01-01 |
| No Prometheus in core | ADR-0014 | T-17-01-02, `pyproject.toml` |
| Plugins trusted; no sandbox claims | ADR-0021 | T-17-02-02 |
| `occurred_at` display; `sequence` order | ADR-0017 | T-17-02-05 |
| Blocking SQLite → executor | ADR-0002 / storage helpers | Audit append |
| Config failures abort, no silent fallback | style / config layer | Alert thresholds |
| plugin_boundary | `.importlinter` | Adapter not in `web/` |

---

## 6. New / touched files (projected)

```
src/lumora_probe/
  bootstrap.py                 # NEW — production composition + PluginServiceAdapter
  __main__.py                  # OPTIONAL — server entry
  cli.py                       # OPTIONAL — `serve` subcommand
  core/
    metrics.py                 # NEW — MetricRegistry
    health.py                  # EXTEND if probe helpers needed
    logging.py                 # EXTEND discipline helpers if needed
    storage.py                 # migrate only if audit schema must grow
    operations.py              # existing audit helper patterns
  web/
    metric_routes.py           # NEW
    health_routes.py           # likely unchanged protocol; provider gains services
    plugin_routes.py           # maybe richer inspect shape
    api.py                     # register metric routes; accept providers
    templates/…                # dashboard partials
tests/
  test_bootstrap.py
  test_phase17_metrics.py
  test_phase17_health.py
  test_phase17_plugin_observability.py
  test_phase17_alerting.py
  test_phase17_audit_log.py
  test_phase17_logging_discipline.py
docs/generated/
  openapi-v1.json              # if routes added
  event-catalog-v1.json        # if plugin diagnostic domain events added
```

---

## 7. Open questions

1. **Server entry:** `lumora serve` vs `python -m lumora_probe` — product preference.
2. **Plugin diagnostics as catalog events:** full domain events vs sink→registry only
   (§0.4). Prefer catalog if plugin metrics must be pure stream projections.
3. **Dashboard charting:** stay Jinja/htmx tables first; chart lib only with ADR-0025
   vendoring if product insists.
4. **Auth-related audit categories:** document N/A until auth ADR; cover real admin
   actions now.
5. **Alert delivery:** in-process API/dashboard (+ structured log) only in Phase 17;
   webhooks/email as plugins later.
6. **LiveEventSource vs EventBus:** confirm bootstrap adapter so UI hub + metric
   subscriber share one bus instance (inspect `web/live.py` / bus protocols when wiring).

Resolved by this review:

- Bootstrap at package root: **yes**
- Import-linter count: **7**
- New observability slice: **no** (unless new ADR)
- Audit table: **use existing `audit_log`**
- Health stack: **extend `HealthRegistry` + existing routes**

---

## 8. Verification strategy

| Gate | Command |
|---|---|
| Full suite | `uv run pytest -q` |
| Phase 17 focus | `uv run pytest tests/test_phase17_* tests/test_bootstrap.py -q` |
| Lint | `uv run ruff check . && uv run ruff format --check .` |
| Import boundaries | `uv run lint-imports --no-cache` (expect **7 kept**) |
| Types | `uv run basedpyright src/lumora_probe/core src/lumora_probe/shared` |
| Assets | `npm run check:assets` if templates/static change |
| Event catalog | `uv run python scripts/generate_event_catalog.py` if events added |
| OpenAPI | regenerate + existing OpenAPI artifact test |
| Adversarial | UI channel saturation / drop accounting if bus subscribers added (`07-definition-of-done.md`) |

### Exit evidence

| Exit criterion | Evidence |
|---|---|
| Metric ≡ event count by construction | T-17-01-04; no independent domain counter API |
| Slow tool → named plugin | Hook timing + plugin health/metrics tests |
| Ready vs live per service | `services[]` populated; ready can 503 while live 200 |
| `app.log` ≠ event mirror | Discipline tests + call-site audit |
| No Prometheus | absent from runtime deps in `pyproject.toml` / lock |
| Audit `12` §10 | Tests + N/A matrix for auth-deferred items |

---

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| New package without ADR fails review | Med | High | Keep metrics in `core`; ADR only if slice forced |
| Metric subscriber adds bus latency | Low | High | UI-channel policy / budgets; adversarial tests |
| Plugin diagnostic catalog bloat | Low | Med | Sink→registry without catalog if needed |
| Audit schema rewrite temptation | Med | Med | Use existing columns + `payload_json` |
| Dashboard asset drift | Med | Low | `check:assets` when assets change |
| Bootstrap only wires plugins, health still empty | Med | Med | Register real probes in same bootstrap pass as T-17-02-01 |

---

## 10. Implementation order

1. **§0 Bootstrap** — plugin adapter + clock + paths (unblocks T-17-02-02)
2. **T-17-01-01** Metric registry in `core`
3. **T-17-01-04** Agreement test (prove design)
4. **T-17-02-01** Wire `HealthRegistry` probes (parallel with 2–3)
5. **T-17-01-02** Metrics API
6. **T-17-02-02** Plugin health rollup
7. **T-17-02-06** Audit coverage gaps (parallel)
8. **T-17-02-04** Alerting thresholds
9. **T-17-02-03** Logging discipline
10. **T-17-01-03** Dashboard
11. **T-17-02-05** Incident investigation polish

---

## 11. References

- `docs/planning/02-phase-plan.md` — Phase 17
- `docs/planning/01-work-breakdown-structure.md` — C-17
- `docs/planning/06-deliverables.md` — Phase 17
- `docs/planning/04-milestones.md` — M13
- `docs/planning/phase-16-completion-report.md` — bootstrap follow-up
- `docs/architecture-baseline/14-observability-architecture.md`
- `docs/architecture-baseline/12-security-architecture.md` §10
- ADR-0012, ADR-0014, ADR-0017, ADR-0021, ADR-0022
- Code: `core/{health,logging,bus,storage,operations}.py`, `web/{api,health_routes,plugin_routes}.py`,
  `plugins/{service,domain,contracts}.py`
