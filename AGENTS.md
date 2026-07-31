# AGENTS.md

Guidance for AI agents working in this repository.

## What this repo is

Two related codebases in one distribution (`lumora-probe`, CPython 3.13+, `uv` + Hatchling):

1. **Lite CLI tools** (shipping): `src/probe_lite/` (DICOM C-STORE/C-ECHO receiver),
   `src/sender_lite/` (one-shot C-STORE/C-ECHO sender), sharing `src/lumora_lite_common/`.
   Entry points: `probe-lite`, `sender-lite` (also `python -m probe_lite` / `python -m sender_lite`).
   Vocabulary for these tools lives in `CONTEXT.md` (Catalog, Study Batch, Study Association, etc.) — use it.
2. **Lumora Probe application** (Phase 20 complete; v0.1.0 GA signed off July 31, 2026):
   `src/lumora_probe/`, module-first slices per ADR-0012. See `CLAUDE.md` for the full
   architecture briefing — it is required reading before touching `src/`.

## Commands

All Python tooling runs through `uv` (deps are locked; use `uv sync --locked` like CI):

```console
uv run pytest -q                          # full test suite
uv run pytest -m unit -q                  # by marker: unit|component|dicom|e2e|interop|slow
uv run ruff check . && uv run ruff format --check .
uv run lint-imports --no-cache            # architecture boundary contracts (7 of them)
uv run basedpyright src/lumora_probe/core src/lumora_probe/shared   # strict mode, these two slices only
```

Frontend assets (committed, CI-verified — see ADR-0025):

```console
npm ci && npm run build:assets            # rebuilds static/ and assets/vendor/
npm run check:assets                      # fails if committed assets drift from a clean build
```

Other scripts: `scripts/generate_fixtures.py` (synthetic DICOM fixtures),
`scripts/generate_event_catalog.py` (regenerates `docs/generated/event-catalog-v1.json`
after event schema changes), `scripts/check-assets.py` (asset-drift gate),
`scripts/spikes/pynetdicom_threading.py` (threading spike harness).

Interop suite is opt-in: `LUMORA_INTEROP=1 uv run pytest -m interop` with
`docker compose -f tests/interop/docker-compose.yml --profile interop up -d`. Never part of the default gate.

## Architecture rules that will bite you

Enforced by import-linter (`.importlinter`) — violations fail CI:

- Each slice owns `domain.py`, `service.py`, `repository.py`, `api.py`, `contracts.py`.
  Other slices may import **only** another slice's `contracts.py`. Slices never import `web`.
- `core` imports no slice; `shared` imports only `core`.
- **`time` and `uuid` may only be imported inside `core/`** (ADR-0022). Everywhere else,
  inject the `Clock` / `IdGenerator` protocols (`core/clock.py`, `core/ids.py`).
  Tests use `SeededUUIDv7Generator` and the doubles in `tests/doubles/` — advance counters, never sleep.
- No `domain.py` imports fastapi/sqlalchemy/jinja2. SQLAlchemy is Core-only (no ORM).

Modeling conventions (ADR-0006):

- Domain: plain Python, no framework. Value objects are `@dataclass(frozen=True, slots=True)`
  with invariants in `__post_init__`; aggregates are plain classes with explicit state
  transitions (see `captures/domain.py`). Aggregates do **not** inherit Pydantic.
- Boundaries: Pydantic v2 (event envelope, config, manifests). Unknown event fields are
  **preserved**, not stripped; unknown `(name, version)` payloads map to an opaque model.

Event system (`shared/events.py`, `core/bus.py`):

- Envelope carries `occurred_at` (wall UTC, display only — **never** for ordering),
  `monotonic_ns` (durations/gaps), `sequence` (gap-free per capture, the only ordering
  authority). See ADR-0017.
- Every event has an `origin`: `observed` vs `client-asserted` (quarantined from analysis).
- One asyncio loop owns the bus; pynetdicom threads publish via `publish_from_thread`.
  Blocking work (parse, SQLite, decode) goes to an executor, never the loop.

## Testing patterns

- Markers from `pyproject.toml`: `unit`, `component`, `dicom`, `e2e`, `interop`, `slow`.
  Weight is at component level: real SQLite/filesystem/pydicom/bus, faking only clock and IDs.
- Tests are flat files in `tests/` named by phase/topic (`test_phase06_*`, `test_sender_*`, ...).
- Golden `.lpcap` fixtures via `tests/golden/harness.py` do **byte comparison** of capture output.
- Test DICOM data is **synthetic only** (`scripts/generate_fixtures.py`, UIDs under
  `1.2.826.0.1.3680043.10.543.*`). Never commit real or de-identified patient data.
- Adversarial tests (kill-mid-capture, UI channel saturation) are required for any new
  concurrency/ordering/drop behavior — see `docs/planning/07-definition-of-done.md`.

## Documentation governance (do not skip)

Three layers, in precedence order: `docs/adr/` (authoritative, 32 ADRs, index in
`docs/adr/README.md`) > `docs/architecture-baseline/` (21 numbered docs) > `docs/planning/`.

- **Deviating from an accepted decision requires a new ADR before the code change** —
  never silently revise an ADR, never work around one with a code comment (CONTRIBUTING.md).
- Several topics are deferred pending their own ADR (pcap import, byte-exact replay, auth/RBAC,
  plugin install over API, Prometheus exposition, PS3.15 de-identification, ...) — do not implement them.
- Contract changes regenerate their artifact (event catalog, etc.) and new domain terms go in
  `docs/architecture-baseline/19-glossary.md`.
- `CLAUDE.md` contains the architecture briefing and current v0.1.0 GA status. The
  implemented application package is `src/lumora_probe/`; older conceptual `lumora/` paths
  in historical ADRs and plans are not filesystem paths.

## Style conventions observed

- `from __future__ import annotations` at the top of every Python file; one-line module docstring.
- Ruff line-length 100, target py313. `StrEnum` for domain enums.
- Config layers: CLI args > env (`PROBE_LITE_*`) / TOML (`sender-lite.toml`) > defaults;
  validation failures abort naming the key and source — never fall back silently.
- Sender Lite exit codes are part of its contract: 0 success, 1 partial/total failure, 2 config/usage, 130 interrupted.
- Non-loopback binds and network exposure stay behind explicit gates (ADR-0010); keep them intact.

## Known inconsistencies to be careful with

- Hatch wheel config references `assets/vendor/**` and `static/**`; these are built by
  `npm run build:assets` and committed. Rebuilding assets produces diffs you must commit.
- `main.py` at the repo root is a placeholder, not an entry point.
