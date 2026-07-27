# ADR-0020: Startup Config Is Immutable; Runtime Settings Are Live and Provenance-Tagged

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

`04` §4 fixes precedence: env > `.env` > TOML/YAML > defaults. `05` §17 makes Settings a
module managing configuration, profiles, preferences, paths and security options, and
`15` §5 puts Settings in primary navigation with plugins contributing settings UI (§17).

So the UI edits settings — but env sits above any file the UI could write. In Docker,
where everything is set by env, a user changes the ring buffer cap in the UI, the app
writes a file, the env var still wins, and the setting appears accepted while doing
nothing. That is precisely the silent failure `03` §12 prohibits.

## Decision

**Two tiers.**

- **Startup config** — bind address, `--trust-network` (ADR-0010), data and capture roots
  (ADR-0011), ports, worker and executor sizing. File and env only, immutable; changes
  require a restart.
- **Runtime settings** — ring buffer cap and retention (ADR-0008), decode cache size
  (ADR-0015), AE/IP allowlist, read-only mode, rule-set toggles (ADR-0018), theme.
  Editable via API and UI, applied live.

**Every setting reports its source**: `default` | `file` | `env` | `runtime`. Anything
pinned by env or file renders as **locked with the source named**, never as an editable
field that silently discards writes. The conflict becomes visible information instead of
a dead control.

**Restart-required settings are refused, not queued.** Attempting to change one returns a
structured error naming the setting, its current source and the restart requirement.
Accept-and-defer is the same silent failure in slower form.

**Runtime settings cannot live in the application database.** ADR-0004 and ADR-0011 made
`index.db` rebuildable — anything stored there must be re-derivable from captures, and
user preferences are not. So runtime settings get their own app-written
`settings.toml` under `LUMORA_DATA_DIR`, separate from operator-authored config and from
the index. Otherwise the first index rebuild silently resets everyone's configuration.

**Config is a boundary, so it is Pydantic** (ADR-0006; `04` §4 already approves
pydantic-settings). Validation failures at startup abort with the offending key and its
source rather than falling back to a default.

**Changes emit `ConfigurationChanged`** with old and new values, redacted where
sensitive — `12` §10 lists configuration changes as auditable, and it lets a capture's
provenance be cross-referenced against the settings in force when it was recorded. That
matters for the case where someone asks why the ring buffer only held four minutes.

**`05` §17's profiles are deferred.** Named config sets are plausible but nothing in the
PRD or personas needs them in v1, and they interact badly with provenance. The extension
point is noted; a later ADR can add them.

## Alternatives Considered

- **Immutable configuration, read-only Settings UI.** Honest, and guts `05` §17.
- **UI writes win.** Rejected: inverts `04` §4 — one of the few genuinely specific
  baseline statements — and would surprise every operator who expects env to be
  authoritative in a container.

## References

`03` §12 · `04` §4 · `05` §17 · `12` §10 · `15` §5, §17 · ADR-0004 · ADR-0006 ·
ADR-0011
