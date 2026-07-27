# ADR-0011: Single `LUMORA_DATA_DIR` Root With OS-Conventional Default

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

The PRD appendix shows `captures/`, `reports/`, `config/`, `docker/` as source-tree
siblings — a development checkout, not an installed application. `04` §4 fixes config
precedence (env > `.env` > TOML/YAML > defaults), which is right for containers.
Nothing says where data goes; `11` never names a path.

## Decision

One root, `LUMORA_DATA_DIR`, OS-conventional by default (XDG on Linux,
`~/Library/Application Support` on macOS, `%APPDATA%` on Windows), overridable by a
single environment variable. Everything derives from it: `index.db`, `app.db`,
`captures/`, `ringbuffer/`, `reports/`, `logs/`, `plugins/`, `settings.toml`.

**Config file discovery is separate from the data root** — configuration may be
read-only or mounted from elsewhere.

Docker mounts one volume. Developers override one variable.

**Load-bearing specifics:**

1. **The captures root is independently overridable**, since evidence is bulky and
   often belongs on another disk. Because the index is rebuildable (ADR-0004),
   relocation is safe by construction. **Additional read-only capture roots** are
   supported — that is how a handed-over `.lpcap` is browsed without importing it,
   which is the vendor-support workflow in `01` §8.
2. **SQLite uses WAL with `busy_timeout`, one writer, and is refused on network
   filesystems.** SQLite over NFS/SMB corrupts. Since the index is a cache, opening it
   on a detected network path is refused with an explanation rather than warned about
   and corrupted later. Captures on a network share remain fine.
3. **The data directory never defaults inside the source tree.** Otherwise a Docker
   bind-mount over `/app` destroys it and `git status` fills with PHI. The container
   runs as a non-root user, so volume ownership is part of the image contract.
4. **Path construction is the real injection surface given no authentication
   (ADR-0009).** Every filesystem path derived from user input gets UUIDv7 format
   validation, then `resolve()`, then an explicit assertion that the result is under an
   allowed root. A `capture_id` of `../../etc` reaching `open()` is the entire exploit
   chain in a v1 with no auth.
5. **A `version` marker is written in the data root**, and a data directory written by
   a newer version is refused rather than mangled.

## Alternatives Considered

- **Repo-relative paths.** Matches the PRD appendix literally; breaks as soon as the
  CLI runs from another directory.
- **OS-conventional multi-root per platform.** Correct for installed apps but splits
  one coherent evidence store across several roots and is awkward in Docker.

## References

`02` Appendix · `04` §4 · `11` · ADR-0004 · ADR-0009
