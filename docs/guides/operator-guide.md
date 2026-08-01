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
- Runtime settings (ring buffer, allowlists, and read-only mode) apply live via
  `/api/v1/settings`; all runtime settings persist to `settings.toml` under the data root. Theme
  and rule toggles are client/UI provenance settings because no server-side analysis rule runner is
  enabled in v1.

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

Readiness is false until event bus, executor, index recovery, databases, capture engine,
DICOM listener, plugin host, and operation jobs are healthy. Poll readiness after start; do not
assume a fixed sleep. A degraded index-recovery detail identifies invalid capture packages that
were skipped while valid captures remained available.

## Shutdown and recovery

Shutdown stops new associations, drains event/capture writers, and persists or explicitly
interrupts active work within the configured grace period. Jobs found `running` after restart
become `Interrupted` and are never auto-resumed (ADR-0023). The capture index is rebuilt from
authoritative capture directories on every startup; `app.db` remains authoritative for jobs,
audit, and bookmarks.

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

## Bounded drain and interruption

On `SIGTERM`, the listener closes admission first. Existing associations, bounded event-bus
thread ingress, capture writers, and durable flushes drain in dependency order. The configured
`shutdown_grace_seconds` is a deadline, not a sleep. If it expires, active captures are sealed as
`interrupted` with `interruption_reason=shutdown deadline`; restart does not report them as
completed.

Inspect `/api/v1/health` and service detail after a restart. For DICOM pressure, inspect listener
counters for `ingress_saturation`, `ingress_timeout`, `ingress_completion_error`, and
`c_store_persistence_failure`. C-STORE outcomes are explicit: malformed input `0xC210`, resource
exhaustion or saturation `0xA700`, internal processing failure `0xC211`, and success `0x0000`.

## Ring-buffer storage and sizing

The persisted ring buffer uses append-only `ringbuffer/segments/segment-*.jsonl` files plus atomic
metadata. Eviction removes expired segments or compacts one affected segment; it does not rewrite
the retained ring as one whole file. The configured byte cap remains hard. Keep free local disk
headroom for one active segment and its metadata rename; SQLite databases must remain on local
storage. Older `records.jsonl` data is migrated only after segment metadata is durably written.
