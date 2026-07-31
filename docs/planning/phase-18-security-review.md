# Phase 18 Security Review

**Date:** 2026-07-31
**Scope:** Public HTTP/WebSocket boundaries, filesystem sinks, secret redaction
**Baseline:** `12-security-architecture.md` §12 (API), §8 (secrets); ADR-0009, ADR-0021

## Authn/Authz

| Topic | Classification |
|-------|----------------|
| Authentication / RBAC | v1 not applicable (ADR-0009) |
| Plugin isolation | Trusted in-process (ADR-0021); capabilities are disclosure only |

## Public route inventory

| Surface | File | Validation notes |
|---------|------|------------------|
| `GET /api/v1` | `web/api.py` | Version root |
| Captures CRUD/list + ring buffer | `web/capture_routes.py` | Query bounds; promote body validated |
| Studies/series/instances collections | `web/collection_routes.py` / `study_routes.py` | Page/page_size bounds; QueryPolicy |
| Study browser | `web/study_routes.py` | Path study_uid; 404 when missing |
| Search | `web/search_routes.py` | `q` max 256; kinds allowlist; page_size ≤ 200 |
| Events list/stream | `web/event_routes.py`, `web/live.py` | Filters, sequence ranges, WS subscribe schema |
| `/ws/ui` | `web/live.py` | Mount/panels/topics; hostile Origin rejected |
| Settings | `web/settings_routes.py` | PATCH body; locked settings refuse |
| Health/ready | `web/health_routes.py` | Read-only |
| Frames/metadata/bookmarks/reports/plugins/metrics/audit/operations | respective `web/*_routes.py` | Provider 404s; structured LumoraError mapping |
| Workspace HTML | `web/workspace_routes.py` | Presentation only |

Unknown event fields remain preserved on envelope boundaries.

## Filesystem sinks

| Sink | Boundary | Containment |
|------|----------|-------------|
| Capture ID → path | `core/paths.resolve_capture_path` | UUIDv7 + `assert_contained` |
| Capture delete | `studies/repository.py` | Roots check + PathSecurityError |
| `.lpcap` unpack | `captures/format.py` | Rejects traversal/symlink members |
| Plugin install CLI | `cli.py` + `plugins/repository.py` | Direct child of plugins root only |
| SQLite DBs | `paths.assert_local_filesystem` | Network FS refused for DBs only |
| Capture roots on shares | ADR-0011 | Allowed; not categorical refusal |

Negative tests: `tests/test_core_infrastructure.py`, `tests/test_phase18_security.py`,
`tests/test_phase06_capture_format.py`, `tests/test_phase06_study_cascade.py`.

## Secret handling

Central processors:

- `core/logging.redact_sensitive` — recursive key redaction including certificate/token shapes
- `settings.runtime._redact_setting_value` — ConfigurationChanged old/new values
- Report DICOM redaction remains ADR-0026 partial redaction (separate from secret leakage)

Gap closed in Phase 18: expanded credential-shaped keys (`client_secret`, `refresh_token`,
`certificate`, `access_key`) with unit coverage.
