# Phase 13 Close-out Implementation Plan — 2026-07-30

**Status:** Executed — see `phase-13-completion-report.md` for acceptance evidence.
**Audience:** Executing agent. Follow the tasks in order. Do not improvise architecture.
**Source analysis:** `docs/planning/phase-13-progress-report.md` plus the exit criteria in
`docs/planning/02-phase-plan.md` (Phase 13, "Exit.") and deliverables in
`docs/planning/06-deliverables.md` (Phase 13).

## 1. What this plan closes

Phase 13 remains open with five blocker groups. This plan resolves them in three waves:

- **Wave 1 — exit-criteria blockers (must all land):**
  - T1: Join live ring-buffer object records into the study browser provider.
  - T2: File-backed application adapter joining verified capture objects to `DicomObjectSource`.
  - T3: Decode duration in an exported report (minimal, Phase-15-safe).
  - T4: Cine playback and fullscreen in the viewer bundle.
  - T5: ADR-0031 (browser test tooling) + opt-in Playwright e2e asserting W/L stays local.
- **Wave 2 — panels and evidence integrity (must land unless explicitly deferred per §8):**
  - T6: `ImageDisplayed` client-asserted post-back from the viewer.
  - T7: Event Timeline panel synchronized by `sequence` over `/ws/ui`.
  - T8: Live Monitor panel (active associations, throughput, `EventsDropped`).
  - T9: Transfer Inspector with per-leg evidence.
  - T10: Bookmark browser UI and API over the existing `bookmarks` table.
  - T11: Command palette (required by risk register R-20; do not defer).
- **Wave 3 — defer candidates (only if Wave 1+2 are accepted first):**
  - Dashboard, Search, notifications, Log Console — deferred via ADR-0032 (see §8).

The recommended resolution is **close the phase properly**, not broad deferral: Phase 14 entry
requires Phase 13 exit, so deferral does not unblock anything; it only converts code debt into
governance debt. Deferral (Wave 3) is the fallback, not the plan.

## 2. Ground rules (violations fail CI; read before every task)

1. `CLAUDE.md` and `AGENTS.md` are required reading. The package is `src/lumora_probe/`.
2. **Never import `time` or `uuid` outside `core/`** (ADR-0022, import-linter enforced). Inject
   `lumora_probe.core.clock.Clock` and `lumora_probe.core.ids.IdGenerator`. Tests use
   `tests/doubles/clock.py` and `tests/doubles/ids.py` — advance counters, never sleep.
3. Slices import only `core`, `shared`, and other slices' `contracts.py`. `web/` imports slices;
   no slice imports `web`. New composition code that touches two slices goes in `web/`.
4. No `domain.py` imports fastapi/sqlalchemy/jinja2. SQLAlchemy is Core-only (no ORM).
5. Every Python file starts with `from __future__ import annotations` and a one-line docstring.
   Ruff line-length 100, target py313. `StrEnum` for new domain enums.
6. **No new runtime dependency.** New *test tooling* (Playwright, T5) requires ADR-0031 **before**
   the dependency is added.
7. After changing event schemas, run `uv run python scripts/generate_event_catalog.py`. After
   changing API surface, regenerate `docs/generated/openapi-v1.json` (see how
   `tests/test_phase08_openapi.py` does it) and commit both artifacts.
8. After changing anything under `assets/source/` or frontend templates that affect the bundle,
   run `npm run build:assets` and commit the rebuilt `static/` output. Verify with
   `npm run check:assets` (must be clean after commit).
9. New domain terms go into `docs/architecture-baseline/19-glossary.md`.
10. Any new concurrency/ordering/drop behavior needs an adversarial test
    (`docs/planning/07-definition-of-done.md`).

### Verification commands (run after every task, in this order)

```console
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run lint-imports --no-cache
uv run basedpyright src/lumora_probe/core src/lumora_probe/shared
npm run check:assets        # only when frontend assets or templates changed
```

Full suite baseline at plan time: 351 passed, 1 skipped. The skip is pre-existing; do not "fix"
it, and do not add new skips.

## 3. Key file and symbol map

| Need | Location |
|---|---|
| Study browser payload builder | `src/lumora_probe/studies/service.py` — `StudyBrowserService.browser()` (line 79), accepts `retention_by_digest: Mapping[str, InstanceRetention]` |
| Retention contract | `src/lumora_probe/studies/contracts.py` — `InstanceRetention` (line 99), `InstanceProvenance` (line 143) |
| Ring-buffer records | `src/lumora_probe/captures/service.py` — `RingBufferService.snapshot()` (line 284), `RingBufferRecord` (line 82), `record_object()` (line 249, stores `study_uid`/`series_uid`/`sop_instance_uid` in `metadata`), `status()` (line 303) |
| Promotion endpoint | `src/lumora_probe/web/capture_routes.py` — `POST /ring-buffer/promote` (line 46), calls `retention_provider.promote_window(...)` |
| Study browser route + provider protocol | `src/lumora_probe/web/study_routes.py` — `StudyBrowserProvider` (line 15), `create_study_browser_router` (line 55) |
| App composition | `src/lumora_probe/web/api.py` — `create_app(...)` (line 161); providers are keyword-injected |
| Object source seam | `src/lumora_probe/studies/repository.py` — `InstanceSourceRepository` protocol (line 269), `InMemoryInstanceSourceRepository` (line 275) |
| Capture object store | `src/lumora_probe/captures/format.py` — `OBJECTS_DIRECTORY = "objects"` (line 28), `path_for(digest)` (line 207), digest-verifying write (line 212) |
| Frame/metadata routes | `src/lumora_probe/web/frame_routes.py` (`FrameProvider`, `InMemoryFrameProvider`), `src/lumora_probe/web/metadata_routes.py` (`MetadataProvider`) |
| Decode evidence | `src/lumora_probe/studies/service.py` — `_publish_decoded` (line 401) emits `ImageDecoded` v1 with `producer="studies.decode"`; `DecodedFrame.duration_ns` in `studies/contracts.py` line 85 |
| Client-asserted endpoint | `src/lumora_probe/web/client_event_routes.py` — `POST /events/client-asserted` (line 97); enforces Viewer category + `origin=client-asserted` |
| Live UI socket | `src/lumora_probe/web/live.py` — `CoalescingGovernor` (line 152), `LiveUpdateHub` (line 401), `create_live_router` (line 442); partials in `web/templates/partials/` (`counters.html`, `status.html`, `timeline.html`) |
| Workspace shell | `src/lumora_probe/web/templates/workspace.html`, `src/lumora_probe/web/workspace_routes.py` |
| Viewer JS bundle source | `assets/source/viewer.js`, `assets/source/cornerstone-renderer.js` |
| Bookmarks table | `src/lumora_probe/core/storage.py` line 140 (`bookmarks`: `bookmark_id`, `name` UNIQUE, `study_uid`, `series_uid`, `capture_id`, `sop_instance_uid`, `created_at`); cascade delete already handled in `studies/repository.py` line 220 |
| Event registry | `src/lumora_probe/shared/events.py` — Viewer category (line 357): `ImageDecoded`, `ImageDisplayed`, `WindowLevelChanged`, `CineStarted` |
| Existing Phase 13 tests | `tests/test_phase13_decode.py`, `test_phase13_frame_api.py`, `test_phase13_studies.py`, `test_phase13_workspace.py` — copy their fixtures and provider-stub patterns |
| Reports slice | `src/lumora_probe/reports/` is currently stubs (3-line files). T3 creates the first real content; Phase 15 owns full reports |

## 4. Wave 1 — exit-criteria blockers

### T1 — Join live ring-buffer records into the study browser provider

**Exit criterion:** "Ring-buffer-backed instances show retention state and offer promotion."

**Problem:** `StudyBrowserService.browser()` already accepts a digest-keyed
`Mapping[str, InstanceRetention]`, and the workspace already renders retention state and an
inline promotion action. Nothing builds that map from live `RingBufferService` records, so
buffer-only instances never surface.

**Implementation:**

1. In `src/lumora_probe/web/` create `retention.py` (composition code touching `captures` and
   `studies` contracts belongs in `web/`, per rule 3). Define:

   ```python
   class RingBufferRetentionMap:
       """Build digest-keyed InstanceRetention from live ring-buffer object records."""

       def __init__(self, ring_buffer: RingBufferService, clock: Clock) -> None: ...

       def retention_by_digest(self) -> dict[str, InstanceRetention]: ...
   ```

2. `retention_by_digest()` logic:
   - Call `ring_buffer.snapshot()` (no filters) and keep records with `kind == "object"`.
   - For each record compute `digest = hashlib.sha256(record.raw).hexdigest()`.
     (`hashlib` is allowed; the ban is on `time`/`uuid` only.)
   - Build `InstanceRetention(source="ring-buffer", ...)` with:
     - `expires_at` = `record.recorded_at + timedelta(seconds=ring_buffer.config.retention_seconds)`.
       Per-record expiry, not the buffer-wide `status().expires_at`, because records age out
       individually.
     - `promotion_start`/`promotion_end` = earliest/latest `occurred_at` across records sharing
       the record's `aggregate_id` (the promotion window the promote endpoint expects). If
       `aggregate_id` is `None`, use the record's own `occurred_at` for both.
     - `aggregate_id` = the record's `aggregate_id`.
   - On digest collision keep the record with the latest `expires_at`.
3. Wire it in the application composition root where `create_app(...)` is assembled (find the
   call site; if only tests assemble the app today, add the wiring in the same module that builds
   `capture_engine`). The study browser provider must pass
   `RingBufferRetentionMap(...).retention_by_digest()` into `StudyBrowserService.browser()` on
   **every request** — ring-buffer state is transient; never cache the map.
4. Buffer-only instances (no projection row) are out of scope for T1 unless the projection
   already contains their UIDs; do **not** invent projection rows. If exit review requires
   buffer-only instances to appear, that is a follow-up task extending the provider to merge
   ring-buffer object metadata (`study_uid`/`sop_instance_uid` in record metadata) as synthetic
   rows marked `retention.state != "permanent"`.

**Tests** (new file `tests/test_phase13_retention_join.py`, marker `component`):

- Real `RingBufferService` with `tests/doubles/clock.py`; record two objects via
  `record_object(...)`; assert the built map yields `source="ring-buffer"`, state `"retained"`
  (expires_at set), `promotable is True`, and correct digests.
- Advance the controllable clock past `retention_seconds`; assert the map treats the record as
  expiring/expired per `InstanceRetention.state` semantics.
- End-to-end through `create_app(study_browser_provider=...)`: `GET
  /api/v1/studies/{uid}/browser` shows retention on an instance whose digest matches a live
  ring-buffer object.

**Commit:** `feat(web): join live ring-buffer retention into study browser`

---

### T2 — File-backed `DicomObjectSource` adapter for verified capture objects

**Blocks:** T3; also named in `phase-12-completion-report.md` follow-ups (it slipped once; this
task makes it tracked Phase 13 P0 work).

**Problem:** `FrameProvider`, `MetadataProvider`, and the decode pipeline consume
`DicomObjectSource`, but the only repository is `InMemoryInstanceSourceRepository`
(`studies/repository.py:275`). A real deployment needs bytes from `captures/<id>/objects/<sha256>`.

**Implementation:**

1. Add `FileSystemInstanceSourceRepository` in `src/lumora_probe/studies/repository.py` (it is a
   repository; keep it in the studies slice, importing only `captures/contracts.py`-visible
   helpers and `core`):

   ```python
   class FileSystemInstanceSourceRepository:
       """Resolve instance IDs to verified capture-owned DICOM bytes."""

       def __init__(self, captures_root: Path, index: <projection lookup>) -> None: ...

       async def get_instance_source(self, instance_id: str) -> DicomObjectSource | None: ...
   ```

2. Lookup flow: instance ID → projection row (`capture_id`, `object_digest`, `frame_count`) via
   the existing instance projection used by `create_projection_routers` → object path via the
   capture object store's `path_for(digest)` (`captures/format.py:207`) → read bytes off-loop
   (`asyncio.to_thread`) → **verify** `sha256(bytes) == digest` before returning; on mismatch
   return `None` and log via structlog (never silently serve unverified bytes — evidence
   integrity rule).
3. Wire as the production `InstanceSourceRepository` at the composition root; keep
   `InMemoryInstanceSourceRepository` for tests.

**Tests** (`tests/test_phase13_instance_source.py`, marker `component`): real temp capture
directory with a synthetically written object; happy path; wrong-digest file returns `None`;
missing capture returns `None`.

**Commit:** `feat(studies): resolve instance sources from verified capture objects`

---

### T3 — Decode duration in an exported report

**Exit criterion:** "Decode duration appears in a capture and a report — it is evidence,
reproducible off the originating machine." The capture side already holds `ImageDecoded`
events with monotonic `duration_ns`; the report side is missing.

**Scope guard:** Phase 15 owns full reports (Jinja, redaction, handover). Do **not** build that.
Build the smallest honest report: a structured JSON capture summary that includes decode timing.

**Implementation:**

1. In `src/lumora_probe/reports/contracts.py` add a Pydantic v2 boundary model:

   ```python
   class CaptureDecodeTiming(BaseModel):
       instance_id: str
       frame_count: int
       total_duration_ns: int
       max_duration_ns: int


   class CaptureSummaryReport(BaseModel):
       report_version: int = 1
       capture_id: str
       generated_from: str  # capture directory path, for reproducibility
       decode_timings: tuple[CaptureDecodeTiming, ...]
   ```

2. In `src/lumora_probe/reports/service.py` add `CaptureSummaryService` with one async method
   `build(capture_id) -> CaptureSummaryReport | None` that reads the capture directory's
   `events.jsonl` **off-loop**, filters `event_name == "ImageDecoded"`, and aggregates
   `duration_ns` per `aggregate_id`. Read via capture contracts/format helpers; never parse
   private slice internals. Unknown envelope fields are preserved automatically by reading raw
   JSON lines — do not re-serialize events.
3. Expose `GET /api/v1/captures/{capture_id}/report` from `src/lumora_probe/reports/api.py`,
   wired in `web/api.py::create_app` with an injected provider (same pattern as
   `create_study_browser_router`). 404 when the capture does not exist.
4. Regenerate `docs/generated/openapi-v1.json` and commit it.
5. Glossary: add "Capture Summary Report" to `docs/architecture-baseline/19-glossary.md`.

**Tests** (`tests/test_phase13_report_timing.py`, marker `component` + one `e2e`):

- Component: synthetic capture directory containing two `ImageDecoded` lines with known
  `duration_ns`; assert aggregated timings appear in the report model.
- E2E over HTTP: decode a real synthetic fixture through the frame endpoint, then
  `GET /api/v1/captures/{id}/report` and assert the decode duration for that instance is present
  and non-zero. This is the exit-criterion assertion — name the test accordingly, e.g.
  `test_decode_duration_appears_in_exported_report`.

**Commit:** `feat(reports): export capture summary with decode timing evidence`

---

### T4 — Cine playback and fullscreen

**Deliverable:** "Client-side W/L, zoom, pan, invert, cine" (`06-deliverables.md`). W/L/zoom/pan
exist in `assets/source/viewer.js`; cine and fullscreen do not.

**Implementation (all client-side; no server changes):**

1. In `assets/source/viewer.js`:
   - Cine: play/pause control that steps frames by calling the **existing** per-frame endpoint
     (`frame_routes.py`; ±2 prefetch is already server-side). Configurable FPS (default 10,
     clamp 1–60). Use `requestAnimationFrame` timing; do not block interaction while cine runs.
     Emit the already-registered `CineStarted` event via the client-asserted endpoint (see T6;
     if T6 is not done yet, leave a single clearly-marked call site guarded by feature check —
     do not fake the event).
   - Fullscreen: toggle on the viewer panel via the Fullscreen API
     (`element.requestFullscreen()` / `document.exitFullscreen()`), with keyboard shortcut `f`
     and an accessible button (`aria-pressed`).
2. Rebuild and commit assets: `npm run build:assets`, then `npm run check:assets` must pass
   after commit.

**Tests:** extend `tests/test_phase13_workspace.py` only for any new template fragments
(buttons/controls rendered). Real playback behavior is validated in T5's browser test.

**Commit:** `feat(viewer): add cine playback and fullscreen toggle`

---

### T5 — ADR-0031 (browser test tooling) + opt-in Playwright e2e

**Exit criterion:** "W/L drag stays within the 100 ms budget with no round trip." This cannot be
honestly asserted without a browser, and `docs/planning/07-definition-of-done.md` forbids new
dependencies without an ADR. So the ADR comes first.

**Step 1 — ADR-0031** (`docs/adr/ADR-0031-browser-e2e-test-tooling.md`):

- Status: Accepted. Context: exit criterion requires browser-validated viewer interaction;
  Python-only tests cannot observe round trips.
- Decision: add Playwright (Python package `pytest-playwright`) as a **dev-only** dependency,
  run under a new opt-in gate mirroring the interop pattern: tests marked `e2e` **and**
  guarded by `LUMORA_E2E=1`, never in the default gate. No runtime dependency; no impact on the
  committed-assets pipeline (ADR-0025).
- Consequences: CI schedules the e2e gate; local default runs unchanged.
- Add it to `docs/adr/README.md` index.

**Step 2 — dependency and config:**

- `uv add --dev pytest-playwright`; `uv run playwright install chromium` (document in the test
  module docstring).
- In `tests/conftest.py` add a skip guard: `e2e` browser tests skip unless `LUMORA_E2E=1`
  (same shape as the existing `LUMORA_INTEROP=1` guard — find it in `tests/test_interop.py` or
  `conftest.py` and copy the pattern).

**Step 3 — the test** (`tests/test_phase13_viewer_e2e.py`, markers `e2e`):

- Boot the ASGI app on an ephemeral port with synthetic fixture data (reuse the fixture
  generation from `tests/fixtures/`).
- Load the workspace, select an instance, perform a synthetic W/L drag via Playwright mouse
  events.
- Assert: (a) the rendered frame updates; (b) **zero** requests to frame/metadata endpoints
  occur during the drag (route request counting via Playwright's `page.on("request")`); (c) a
  coarse wall-time check that 30 drag frames complete well under budget (this is a smoke bound,
  not a precision benchmark — ADR-0030 owns ratified budgets).

**Commit:** two commits — `docs(adr): accept browser e2e test tooling (ADR-0031)` then
`test(viewer): assert window/level interaction needs no round trip`.

## 5. Wave 2 — panels and evidence integrity

All panels are views in `web/` over existing slices. They get **no new package** (ADR-0012).
Live data flows through `/ws/ui` via `LiveUpdateHub` + `CoalescingGovernor` (`web/live.py`);
server-rendered fragments go in `web/templates/partials/` with targeted out-of-band swaps.
Reuse the existing partials (`counters.html`, `status.html`, `timeline.html`) rather than
inventing a parallel mechanism.

### T6 — `ImageDisplayed` client-asserted post-back

**Why non-deferrable:** ADR-0016 quarantine is evidence-integrity spine; the exit-relevant
claim "client-asserted events are quarantined" is only auditable once such events flow.

1. The endpoint exists: `POST /api/v1/events/client-asserted`
   (`web/client_event_routes.py:97`), enforcing Viewer category and
   `origin=EventOrigin.CLIENT_ASSERTED`. Do not modify it unless the `ImageDisplayed` v1
   payload schema is undefined — if it is, define it in `shared/events.py` (payload:
   `instance_id`, `frame_number`, `capture_id`), regenerate `docs/generated/event-catalog-v1.json`
   via `scripts/generate_event_catalog.py`, and commit the artifact.
2. In `assets/source/viewer.js`, after a frame is rendered (not on W/L drag), POST
   `ImageDisplayed` v1 with the payload above. Fire-and-forget; never block rendering on it.
3. Rebuild and commit assets.

**Tests** (`tests/test_phase13_image_displayed.py`):

- API-level: POST a valid `ImageDisplayed`; assert the stored/published envelope has
  `origin == "client-asserted"` and `producer == "web-ui"`.
- Quarantine: assert analysis-facing consumers exclude it — concretely, that the study browser
  payload and the T3 report builder ignore events with `origin=client-asserted` (add a
  client-asserted `ImageDisplayed` line to the T3 fixture and assert it changes nothing).

**Commit:** `feat(viewer): post back quarantined ImageDisplayed evidence`

### T7 — Event Timeline panel synchronized by `sequence`

1. Server: subscribe a timeline UI channel to the bus via `LiveUpdateHub`; append envelopes to
   the existing `partials/timeline.html` fragment with an HTMX out-of-band swap, **ordered by
   `envelope.sequence`, never `occurred_at`** (ADR-0017). Cap the DOM (drop oldest beyond the
   governor's cap; surface the `EventsDropped` counter — see T8).
2. Template: extend `workspace.html` dock to host the fragment; keyboard navigable rows.

**Tests** (`tests/test_phase13_timeline.py`, marker `component`): publish events with
out-of-order `occurred_at` but in-order `sequence`; assert rendered order follows `sequence`.
**Adversarial (required):** saturate the UI subscription; assert the rendered sequence gap
equals the `EventsDropped` count (pattern exists from Phase 09/11 tests — find the saturation
test and copy its harness).

**Commit:** `feat(web): synchronize event timeline by sequence`

### T8 — Live Monitor panel

1. Data sources, all existing: active associations from the associations projection store
   (injected into `create_app` as `association_store`), throughput from bus counters, dropped
   count from the governor's `EventsDropped` counter.
2. Render into `partials/status.html` / `partials/counters.html` with latest-wins semantics for
   status and aggregation for counters (the governor already implements both — reuse, do not
   rebuild).

**Tests** (`tests/test_phase13_live_monitor.py`, marker `component`): with two active
associations in the store, the fragment lists both; after forcing governor drops, the counter
fragment shows the exact drop count.

**Commit:** `feat(web): add live monitor associations and drop counters`

### T9 — Transfer Inspector with per-leg evidence

1. Composition service in `web/` (e.g. extend `web/service.py` or add `web/transfer_inspector.py`):
   for a selected instance/association, join (a) association legs from the associations slice
   contracts, (b) receive/persist evidence (`InstancePersisted` etc. from the event store),
   (c) decode evidence (`ImageDecoded`, observed origin only). Join by `correlation_id` /
   `aggregate_id`; present per-leg rows with duration arithmetic on `monotonic_ns` only.
2. Read-only REST endpoint under `/api/v1` returning the composed legs, plus a workspace panel
   consuming it. Regenerate `docs/generated/openapi-v1.json`.

**Tests** (`tests/test_phase13_transfer_inspector.py`, marker `component`): fixture with one
association and one decoded instance; assert both legs appear with correct ordering and that a
`client-asserted` event is excluded from the evidence rows.

**Commit:** `feat(web): add transfer inspector with per-leg evidence`

### T10 — Bookmark UI and API

1. The table exists (`core/storage.py:140`, `app.db` — authoritative, ADR-0023). Add a
   repository in `studies/repository.py` next to the cascade code that already touches
   `bookmarks`: `add_bookmark`, `list_bookmarks(capture_id=None)`, `remove_bookmark`. Injected
   `Clock` + `IdGenerator` for `created_at`/`bookmark_id`.
2. REST: `POST /api/v1/bookmarks`, `GET /api/v1/bookmarks`, `DELETE /api/v1/bookmarks/{id}`
   from a new router following the existing route-module pattern; wire in `create_app`.
   Enforce the `UNIQUE(name)` conflict as a structured `LumoraError` (409-class), not a 500.
3. UI: bookmark action on study browser rows (button in the existing workspace instance list)
   and a bookmark list panel that navigates to the stored study/instance on click.
4. Regenerate `docs/generated/openapi-v1.json`. Rebuild/commit assets if templates changed.

**Tests** (`tests/test_phase13_bookmarks.py`, marker `component`): create/list/delete round
trip; duplicate name returns the structured error; capture cascade delete removes
capture-scoped bookmarks but retains study-scoped ones (semantics already recorded at
`studies/repository.py:230`).

**Commit:** `feat(studies): add bookmark persistence API and browser actions`

### T11 — Command palette

**Do not defer:** risk register R-20 makes Phase 18 keyboard-only P0 conditional on the palette
existing in Phase 13. Deferring requires amending R-20 — not worth it; the palette is thin.

1. Client-side palette (Alpine.js, already vendored) in `workspace.html`: `Ctrl+K`/`Cmd+K`
   opens; actions are navigation + existing API calls only (open study, open capture, focus
   panel, toggle theme, promote selection). Fully keyboard operable; `Esc` closes; focus
   returns to the invoking element.
2. No new server endpoints. Keep the action table in one JS module under `assets/source/` so
   Phase 18 can extend it.

**Tests:** template-level assertions in `tests/test_phase13_workspace.py` (palette markup,
ARIA roles); interaction correctness is covered by extending the T5 e2e spec with one
keyboard-driven navigation.

**Commit:** `feat(web): add keyboard-first command palette`

## 6. Wave 3 — defer candidates (fallback only)

If Waves 1–2 are complete and verified but schedule requires closing the phase, the following
may be deferred: **Dashboard, Search, notifications, Log Console**. All four are additive views
with no downstream phase dependency.

Deferral procedure (all steps required; partial deferral is not allowed):

1. Write `docs/adr/ADR-0032-phase-13-panel-deferral.md`: status Accepted; lists exactly which
   panels defer to which phase; states that no exit criterion depends on them (verify against
   `02-phase-plan.md` Phase 13 "Exit." — if any does, stop and build it instead).
2. Index it in `docs/adr/README.md`.
3. Update `docs/planning/06-deliverables.md` and `04-milestones.md` with a pointer to ADR-0032.
4. Record the deferral in the Phase 13 completion report.

## 7. Execution order and dependencies

```text
T1 (retention join) ──────────────┐
T2 (instance source adapter) ──► T3 (report timing)          Wave 1: T1, T2, T4 parallel;
T4 (cine/fullscreen)              T5 ADR before T5 code       T3 after T2; T5 ADR first
T5 (ADR-0031 + e2e)  ── validates T4 and exit criterion 5
T6 (ImageDisplayed) ── needed by T9 quarantine test           Wave 2: T6, T10, T11 parallel;
T7 (timeline) ──┐                                          T7 before T8 (shares governor);
T8 (live monitor) ─┴─ T9 (transfer inspector) last         T9 last (joins the most data)
Wave 3 deferral only after Wave 1+2 verified
```

Each task ends with: focused tests → full verification command list (§2) → single commit with
the message given. Do not batch multiple tasks into one commit.

## 8. Phase close-out checklist (after the last task)

1. Full gate: `uv run pytest -q` (expect ≥ previous 351 + new tests, still only the 1
   pre-existing skip), ruff, ruff format, `lint-imports --no-cache`, basedpyright on
   `core`+`shared`, `npm run check:assets`.
2. `LUMORA_E2E=1 uv run pytest -m e2e` passes with Chromium installed.
3. Regenerated artifacts committed: `docs/generated/openapi-v1.json`,
   `docs/generated/event-catalog-v1.json` (if any event schema changed), rebuilt `static/`.
4. Glossary updated (`19-glossary.md`) for: Capture Summary Report, plus any new terms.
5. Map every exit criterion to its proof in the completion report:

   | Exit criterion | Proof |
   |---|---|
   | Decode duration in capture and report | T3 e2e test name + report artifact |
   | Study spanning three captures never whole | existing provenance tests + workspace partial test |
   | Ring-buffer retention state + promotion | T1 tests |
   | Duplicate UID finding with both digests | existing `test_phase13_studies.py` |
   | W/L within 100 ms, no round trip | T5 e2e spec |
   | Undecodable syntax explains why | existing `test_phase13_decode.py` |

6. Write `docs/planning/phase-13-completion-report.md` (new file; do not overwrite the progress
   report), referencing ADR-0031 (and ADR-0032 if Wave 3 was used).
7. Only then may Phase 14 begin (its entry also requires Phase 12 exit, already accepted).

## 9. Explicit non-goals for the executing agent

- Do not start Phase 14 analysis work (rule engine, condition registry, ADR-0028 in the
  baseline numbering — note the repo's local ADR-0028 is a different, Lite-scope document;
  do not confuse them).
- Do not build full Phase 15 reports (Jinja, redaction, export pipelines) beyond T3's JSON
  summary.
- Do not implement any deferred-pending-ADR topic listed in `CLAUDE.md` (pcap import,
  byte-exact replay, auth/RBAC, plugin install over API, Prometheus, PS3.15 de-identification).
- Do not refactor existing Phase 13 code beyond what a task requires; gates are green — keep
  them green.
