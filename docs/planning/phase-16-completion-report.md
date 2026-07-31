# Phase 16 — Plugin SDK Completion Report

**Date:** 2026-07-31
**Status:** Complete

## Completed work

### WP-16-01 — Public hook surface

- Added pluggy hook specifications for event observation, analysis, report contributions,
  command metadata, and settings metadata.
- Added immutable public DTOs for events, analysis contexts, findings, reports, commands,
  settings, and plugin diagnostics.
- Added manifest validation for identity, SDK major range, entry point, hooks, and disclosed
  capabilities.
- Documented SDK `1.0`, major compatibility policy, and a two-minor-release deprecation window.

### WP-16-02 — Loader and containment

- Added deterministic discovery from the configured plugin root, with disabled-by-default
  state persisted in `.plugin-state.json`.
- Added load-time entry-point and declared-hook validation plus SDK-major refusal.
- Added per-hook exception containment. Failures emit `ErrorRaised` diagnostics with plugin ID
  and hook, and repeated failures auto-disable the plugin.
- Added injected monotonic hook budgets. Breaches emit `WarningRaised` diagnostics and repeated
  breaches auto-disable the plugin. The SDK documents that in-process execution cannot be
  interrupted.
- Added restart-scoped enable/disable management.
- Added API list/inspect/enable/disable routes. No API installation route exists.
- Added CLI filesystem installation and explicit trust disclosure in the workspace UI.

### WP-16-03 — Seed rules re-homed

- Ported all eight Phase 14 seed rule families to `plugins.bundled_rules` using only public
  SDK DTOs and hook implementations.
- Added `RuleEngine.evaluate_plugin` as the analysis-side adapter that preserves observed-event
  filtering, citation validation, finding invariants, and deterministic ordering.
- Recorded the extension-point gap report. No Phase 14 seed rule required privileged access.

## Design decisions

- Plugin boundary modules retain the repository's empty `__all__` convention; public names are
  available through module attributes and the package facade without turning architecture
  boundary modules into wildcard-export surfaces.
- Hook timing uses a host-injected monotonic protocol. Production composition supplies the core
  clock; tests use deterministic clock doubles. This preserves ADR-0022's time-import boundary.
- Manifest capabilities are disclosure only. The implementation does not claim capability
  enforcement, consistent with ADR-0021.
- Installation is a deliberate filesystem/CLI action. Enabling imports code and therefore takes
  effect only after restart.

## Files added

- `src/lumora_probe/plugins/bundled_rules.py`
- `src/lumora_probe/web/plugin_routes.py`
- `tests/test_phase16_plugin_sdk.py`
- `tests/test_phase16_bundled_plugins.py`
- `tests/test_phase16_plugin_management.py`
- `docs/plugins/sdk.md`
- `docs/plugins/extension-point-gap-report.md`
- `examples/plugins/example_plugin/manifest.json`
- `examples/plugins/example_plugin/plugin.py`
- `examples/plugins/example_plugin/README.md`
- `docs/planning/phase-16-completion-report.md`

## Files modified

- `src/lumora_probe/plugins/{__init__,api,contracts,domain,repository,service}.py`
- `src/lumora_probe/analysis/service.py`
- `src/lumora_probe/cli.py`
- `src/lumora_probe/web/api.py`
- `src/lumora_probe/web/templates/workspace.html`
- `pyproject.toml`, `uv.lock`
- `docs/architecture-baseline/19-glossary.md`
- `docs/planning/06-deliverables.md`
- `docs/generated/openapi-v1.json`

## Tests and quality gates

- Focused Phase 16 suite: **9 passed**.
- Full suite: **463 passed, 2 skipped**.
- Ruff lint: passed.
- Ruff format check: passed.
- Import-linter: **7 contracts kept, 0 broken**.
- BasedPyright (`core` and `shared`): **0 errors, 0 warnings, 0 notes**.
- Asset drift check: passed; committed assets unchanged.
- OpenAPI artifact test: passed after regeneration.

## Acceptance evidence

| Exit criterion | Evidence |
|---|---|
| Seed rules run on public extension points | `test_bundled_seed_rules_are_public_sdk_analyzers`; `test_rule_engine_accepts_bundled_plugin_through_public_sdk_adapter` |
| Raising plugin cannot propagate into core | `test_repeated_plugin_failures_emit_error_and_disable` |
| Slow plugin warns and auto-disables | `test_slow_plugin_warns_and_is_disabled_after_repeat` |
| No API route installs a plugin | `test_plugin_api_lists_and_changes_restart_scoped_state_without_install_route`; regenerated OpenAPI artifact |
| UI states trust/no capability enforcement | `test_workspace_contains_explicit_plugin_trust_disclosure` |

## Known limitations

- Plugins are trusted in-process code. Capability declarations are not sandbox permissions;
  infinite loops can still stall the event loop, as required by ADR-0021.
- The plugin management provider is injected at application composition time. Durable production
  bootstrap wiring from `StartupConfig.data_dir` is reserved for the application composition
  work that consumes the SDK; the repository/service are ready for that injection.
- Plugin installation accepts a deliberately selected directory, not a package repository or
  API upload. Remote repositories and API installation remain deferred by ADR-0021.
- The default `PluginService` has no implicit clock; production composition must inject the core
  monotonic clock to activate budget measurement. This keeps time ownership in `core`.

## Follow-up recommendations

- Wire `PluginService(PluginRepository(config.data_dir / "plugins"), clock=core_clock)` into the
  production application bootstrap before Phase 17's per-plugin observability work.
- Add event-derived plugin metrics and health exposure in Phase 17; do not duplicate event
  instrumentation in this phase.
