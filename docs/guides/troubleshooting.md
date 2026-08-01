# Troubleshooting Guide

Diagnostic conditions use stable IDs from [`docs/condition-catalogue-v1.md`](../condition-catalogue-v1.md)
and the generated catalogue. Prefer those IDs when an observed Condition is emitted. Do not invent
condition IDs for ordinary operational errors.

## Startup and configuration

| Symptom | Likely cause | Remediation |
|---------|--------------|-------------|
| Process aborts naming a setting | Invalid startup config | Fix the named key at the named source; do not expect silent defaults |
| Non-loopback bind refused | Exposure gate | Pass `--trust-network` only after accepting no-auth risk |
| Data directory refused as newer | Version marker mismatch | Upgrade Lumora Probe before opening that data root |

## Readiness failures

| Symptom | Likely cause | Remediation |
|---------|--------------|-------------|
| `/api/v1/health/ready` not ready | Event bus, index recovery, DICOM listener, or database probe not ready | Check the named service detail; confirm `index.db`/`app.db` initialised on a local filesystem and that the DICOM port is free |
| Readiness reports degraded index recovery | One or more malformed capture packages were skipped | Preserve the capture root, inspect startup diagnostics, repair or quarantine the invalid package, then restart to rebuild the derived index |
| Liveness OK, readiness fail | Intentional split | Investigate the failing probe named in the health payload |

## Data root and network filesystems

| Symptom | Likely cause | Remediation |
|---------|--------------|-------------|
| `LUMORA-CORE-PATH-001` | SQLite path on network filesystem | Move `LUMORA_DATA_DIR` (for databases) to local disk; captures may remain on a share |
| Capture path escape errors | Invalid capture ID or traversal | Use UUIDv7 capture IDs from the API; never pass caller-controlled relative paths |

## Rebuild and recovery

| Symptom | Likely cause | Remediation |
|---------|--------------|-------------|
| Study browser empty after restore | Missing or stale `index.db` | Rebuild projections from capture directories |
| Job stuck Interrupted | Restart mid-operation | Start a new operation; interrupted jobs are never auto-resumed |

## Dropped UI events

UI/WebSocket channels use bounded drop-oldest queues. When drops occur, the UI surfaces
`EventsDropped` and sequence gaps must reconcile with that count. Capture persistence does
**not** silently drop. Saturating the UI channel is not a capture integrity failure.

## Replay refusal

Protocol replay refuses captures without the required fidelity stream, refuses targets not
on the allowlist, refuses concurrent exclusive replay, and refuses dry-run violations of
policy. Read the structured error’s remediation field.

## Dependency / audit exceptions

Python dependency audit is a hard CI gate. npm audit is report-only in Phase 18 unless a
blocking step is separately approved. Reviewed exceptions live in
`docs/planning/phase-18-dependency-audit.md`.

See also: [operator-guide.md](operator-guide.md), [user-workflows.md](user-workflows.md).

## DICOM saturation and shutdown

| Symptom | Likely cause | Remediation |
|---------|--------------|-------------|
| C-STORE returns `0xA700` | Bounded event ingress, persistence capacity, or event-admission timeout | Stop or reduce senders, inspect listener counters, and retry after pending submissions drain |
| C-STORE returns `0xC210` | Malformed or incomplete DICOM payload | Correct the sender payload; this response is not a successful persistence claim |
| C-STORE returns `0xC211` | Unexpected event completion or processing failure | Preserve logs/correlation ID, inspect `ingress_completion_error`, and retry only after root cause is understood |
| Capture manifest is `interrupted` | Shutdown grace deadline expired while work was active | Restart with the same data root; retain the interrupted evidence and do not relabel it completed |
| Warning appears from a third-party DICOM transport | Runtime/library compatibility warning | Run the locked dependency line and capture the full warning under `-W default`; do not hide warnings with a global filter |

## Pagination and rebuild workload

Collection APIs use SQL-backed count/page queries and whitelist sort/filter fields. If a page is
slow, record endpoint, page size, filter, local-disk identity, and database size. Do not move
`index.db` or `app.db` to a network filesystem; that deployment remains unsupported. Projection
rebuild reads authoritative capture packages and recreates derived index state.
