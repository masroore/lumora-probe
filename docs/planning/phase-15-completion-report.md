# Phase 15 — Reports Completion Report

**Date:** 2026-07-30  
**Status:** Complete  
**Phase:** 15 — Reports  
**Milestone:** M12 Beta Ready

## Completed work

### WP-15-01 — Report generation

- Added deterministic Pydantic report contracts for conditions, findings, timings,
  provenance, rule-set versions, rendered artifacts, and progress checkpoints.
- Added read-only capture evidence repository for `manifest.json`, `events.jsonl`, and
  regenerable `analysis/findings.json`.
- Added Jinja HTML and Markdown templates plus JSON rendering.
- Preserved the Phase 13 capture-summary JSON route and extended the report service without
  changing its observed-only timing behavior.
- Added finding citation validation against captured event sequence numbers.
- Added background generation through the shared in-memory operation registry.
- Added durable report artifact files under the injected reports root, atomic writes, and
  operation outcomes.
- Added `ReportProgressed` and `ReportGenerated` bus integration. Report progress uses the
  job registry's existing durable checkpoint and event path; report generation never
  auto-resumes after restart.
- Added `POST /api/v1/captures/{capture_id}/report` returning `202` and an operation ID.
  Existing `GET /api/v1/captures/{capture_id}/report` remains compatible.

### WP-15-02 — Redaction

- Added configurable tag-level redaction profiles with remove and replacement actions.
- Applied profiles to deep copies only.
- Added consistent Study/Series/SOP Instance UID remapping across nested references and
  multiple objects using injected identity sources.
- Added new-capture redaction output with source capture ID, profile, warning metadata,
  verified object inventory, and unchanged source package.
- Added explicit warnings for `BurnedInAnnotation`, Secondary Capture, Ultrasound,
  screenshot-like content, unrecognized private tags, and free-text fields.
- Product terminology uses `redact`; no PS3.15 conformance claim is made.

### WP-15-03 — Handover export

- Added safe default handover export at `fidelity: events`.
- Default export copies event evidence and protocol traces, retains only a whitelisted
  manifest metadata subset, and omits object data and the object inventory.
- Added deliberate `pixel_bearing=True` opt-in. The output manifest marks the opt-in and
  source provenance; the source package remains unchanged.
- Added vendor handover workflow documentation and final pre-transfer checks.

## PDF decision (U-08)

HTML is the canonical printable report. Operators use browser **Print → Save as PDF**.
The server does not add a PDF dependency and does not promise byte-identical PDF output
across browsers. Markdown remains the portable text form.

## Files added

- `src/lumora_probe/captures/handover.py`
- `src/lumora_probe/reports/jobs.py`
- `src/lumora_probe/reports/redacted_capture.py`
- `src/lumora_probe/reports/redaction.py`
- `src/lumora_probe/reports/templates/report.html.j2`
- `src/lumora_probe/reports/templates/report.md.j2`
- `tests/test_phase15_handover.py`
- `tests/test_phase15_redacted_capture.py`
- `tests/test_phase15_redaction.py`
- `tests/test_phase15_report_jobs.py`
- `tests/test_phase15_reports.py`
- `docs/guides/vendor-handover.md`
- `docs/planning/phase-15-completion-report.md`

## Files modified

- `src/lumora_probe/core/operations.py`
- `src/lumora_probe/reports/__init__.py`
- `src/lumora_probe/reports/api.py`
- `src/lumora_probe/reports/contracts.py`
- `src/lumora_probe/reports/domain.py`
- `src/lumora_probe/reports/repository.py`
- `src/lumora_probe/reports/service.py`
- `src/lumora_probe/shared/events.py`
- `src/lumora_probe/web/api.py`
- `src/lumora_probe/web/report_routes.py`
- `docs/architecture-baseline/06-event-driven-architecture.md`
- `docs/generated/event-catalog-v1.json`
- `docs/generated/openapi-v1.json`

## Tests and quality gates

- Full default suite: **453 passed, 2 skipped**.
- Phase 15 focused suite: **16 passed**.
- Ruff lint: passed.
- Ruff format check: passed.
- Import-linter: **7 kept, 0 broken**.
- BasedPyright required strict scope (`core`, `shared`): **0 errors, 0 warnings, 0 notes**.
- Source distribution and wheel build: passed.
- OpenAPI artifact regenerated and matches `create_app().openapi()`.
- Event catalog regenerated after adding `ReportProgressed`.

## Acceptance evidence

| Criterion | Evidence |
|---|---|
| Default export contains no pixel data | `tests/test_phase15_handover.py` verifies no object inventory/data in the default package. |
| Pixel export requires explicit opt-in | The exporter defaults to `pixel_bearing=False`; tests verify explicit labeling. |
| Redaction creates a new capture | `tests/test_phase15_redacted_capture.py` verifies new ID and `source_capture_id`. |
| Source remains untouched | Redaction and handover tests compare source manifest/events/object bytes. |
| UID hierarchy survives redaction | Redaction tests verify shared Study/Series mappings and distinct SOP mappings. |
| Unverifiable content is flagged | Redaction tests cover burned-in annotation, SOP classes, private tags, free text, and screenshot modality. |
| Reports carry rule-set version | Report contract, template, and report-service tests verify it. |
| Progress rides the bus | Report-job tests assert `ReportProgressed`, durable job state, and `ReportGenerated`. |
| No inferred finding enters `events.jsonl` | Existing Phase 14 purity tests remain green; report generation reads evidence without mutation. |
| Client-asserted timing/evidence remains excluded | Existing Phase 13 report tests and Phase 15 report assembly preserve quarantine. |
| No server-side PDF dependency | Vendor handover guide records the browser print-to-PDF decision. |

## Known limitations and follow-up

- Report artifact download is currently a service/reports-root concern; the API returns the
  operation ID and the existing operation endpoint exposes job state. A dedicated artifact
  download route can be added in a later API slice if required by the product surface.
- Pixel-bearing handover copies source object bytes and is not a redaction operation. The
  handover guide requires tag-level redaction first when an object-bearing redacted package
  is needed.
- Tag-level redaction is intentionally not a PS3.15 profile and cannot inspect or alter
  identifiers burned into pixels.
- Interop and browser E2E suites remain opt-in under repository policy.
- Strict BasedPyright remains scoped to `core` and `shared`, matching the repository's
  established quality-gate command; touched report/capture behavior is covered by Ruff and
  component tests.

## Follow-up recommendation

Begin Phase 16 only after reviewing this report and accepting the documented report-artifact
API limitation. Do not add plugin installation or standards-based redaction claims to Phase
15 retroactively.
