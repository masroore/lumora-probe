# Upgrade and Migration Guide

Lumora Probe keeps one data root per installation. Set `LUMORA_DATA_DIR` explicitly when
upgrading a workstation, container, or air-gapped deployment so the new process opens the
same evidence store.

## Before upgrading

1. Stop Lumora Probe and allow active associations and writers to drain.
2. Back up `app.db`.
3. Preserve `captures/`, `ringbuffer/`, and retained `.lpcap` packages according to the
   operator's evidence-retention policy.
4. Keep the data-root `version` marker with the data directory.

`app.db` contains authoritative job, audit, and bookmark records. Capture directories are
also authoritative evidence; an `app.db` backup does not replace them. `index.db` is a
rebuildable projection and is not a substitute for either backup.

## Installation upgrade

Install the new wheel or image without running Node:

```console
uv pip install lumora-probe==<version>
```

For Docker, keep the single `/var/lib/lumora` volume and set `LUMORA_DATA_DIR` to that
mount. The image runs as the documented non-root `lumora` user; the mounted directory must
be writable by that UID/GID.

Start the new version and poll `/api/v1/health/ready`. Do not use a fixed sleep as a
readiness check.

## Database behavior

- **`app.db`** is migrated idempotently at startup. Existing tables and records are kept;
  the application schema marker is advanced only after the schema script succeeds.
- **`index.db`** is derived from captures. If it is missing or needs recovery, it may be
  rebuilt from capture evidence; do not treat it as the authoritative record.
- **`version`** is the data-directory compatibility marker. The current supported marker is
  `1`. A marker greater than the running application's supported version is refused before
  the directory is used. Lumora Probe does not downgrade or mangle a newer data directory.

If startup reports a version mismatch, install a compatible newer Lumora Probe release or
restore a copy of the data directory that matches the running version. Do not edit the
marker as a first-line workaround.

## Recovery notes

If an index is lost or corrupt, stop the service, preserve the failing directory for
investigation, and rebuild the projection from the authoritative capture directories using
the release's documented recovery procedure. Keep `app.db` and captures intact while doing
so. Network filesystems remain unsupported for SQLite databases; relocate `LUMORA_DATA_DIR`
to local storage and leave only bulky capture roots on a share when required.

See [operator-guide.md](operator-guide.md), [deployment-topologies.md](deployment-topologies.md),
and ADR-0011 for the data-root and storage contract.

## Ring-buffer format migration and rollback

Newer releases persist ring evidence under `ringbuffer/segments/` with an atomic metadata file.
On first open, a legacy `records.jsonl` is read and migrated to segments; the legacy file is not
deleted until the new metadata is durable. Stale temporary files from an interrupted rotation are
ignored or cleaned during the next open. A data root with a newer unsupported ring format is
refused rather than silently downgraded.

For rollback, stop admission, wait for bounded drain, copy the complete `ringbuffer/` and
`captures/` trees, then install the prior version. Preserve the newer tree as an investigation
copy; never hand-edit segment metadata or delete `app.db` as a rollback shortcut.
