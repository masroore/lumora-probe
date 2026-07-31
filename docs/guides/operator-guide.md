# Operator Guide

## Startup and configuration

Precedence: environment > `.env` > TOML/YAML > defaults. Validation failures **abort** and
name the offending key and source.

```console
LUMORA_DATA_DIR=/var/lib/lumora lumora serve
lumora serve --host 127.0.0.1 --port 8000
lumora serve --trust-network --host 0.0.0.0   # explicit non-loopback acknowledgment
```

- Startup-only settings (bind address, data/capture roots, ports, executor sizing) require
  restart to change.
- Runtime settings (ring buffer, allowlists, read-only mode, theme, rule toggles) update live
  via `/api/v1/settings` and persist to `settings.toml` under the data root.

## Exposure gate and read-only mode

- Default bind is loopback. Non-loopback requires `--trust-network` / the matching env flag.
- Read-only mode is a server-wide gate that refuses mutating HTTP methods.

## Data-root layout

Everything derives from `LUMORA_DATA_DIR` (OS-conventional default when unset):

| Path | Role |
|------|------|
| `index.db` | Derived study/series/instance projections and rolling event window. **Rebuildable.** |
| `app.db` | Job history, audit log, bookmarks. **Authoritative; back this up.** |
| `captures/` | Capture directories (authoritative evidence) and imported `.lpcap` packages |
| `ringbuffer/` | Always-on rolling evidence buffer |
| `reports/`, `logs/`, `plugins/`, `settings.toml` | Derived or operator-managed artifacts |

**Filesystem precision (ADR-0011):**

- SQLite databases (`index.db`, `app.db`) are **refused on detected network filesystems**.
- Capture directories **may** live on network shares when configured.
- Backing up `app.db` does **not** replace preserving Capture directories. Captures are
  authoritative evidence and must follow the operator’s retention obligations.

## Health and readiness

- Liveness/health: `GET /api/v1/health`
- Readiness: `GET /api/v1/health/ready`

Poll readiness after start; do not assume a fixed sleep.

## Shutdown and recovery

Shutdown drains associations and durable writers within the configured grace period. Jobs
found `running` after restart become `Interrupted` and are never auto-resumed (ADR-0023).

## Backup checklist

1. Stop or quiesce writers when taking a consistent snapshot if your storage layer requires it.
2. Back up `app.db`.
3. Preserve Capture directories (and any `.lpcap` exports you retain).
4. Treat `index.db` as disposable; rebuild from captures if needed.
5. Record plugin directories you installed deliberately.

Cross-links: [capture-engine.md](../capture-engine.md), [vendor-handover.md](vendor-handover.md),
[deployment-topologies.md](deployment-topologies.md),
[privacy-and-compliance-posture.md](privacy-and-compliance-posture.md).

Upgrade and recovery details: [upgrade-and-migration.md](upgrade-and-migration.md).
