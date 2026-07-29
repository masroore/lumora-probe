# ADR-0028: Shared `lumora_lite_common` Library for the Lite Tools

- **Status:** Accepted
- **Date:** 2026-07-29
- **Scope:** Probe Lite and Sender Lite (the Lite tools); does not affect the parent `lumora/` project

## Context

Probe Lite and Sender Lite were originally written as deliberately self-contained packages.
The Sender Lite implementation plan and an inline note in `src/sender_lite/log.py` forbade
introducing shared infrastructure between the two, so each package carried its own copy of
several small, byte-identical helpers. As both tools matured, the duplication proved to be
accidental cost rather than intentional isolation:

- **Logger engine** — `ProbeLogger` and `SenderLogger` share an identical
  `event`/`info`/`warning`/`error` engine and `_text_value` helper; only the
  event-name → human-label map differs.
- **Signal handling** — `_install_signal_handlers` / `_restore_signal_handlers` are
  structurally identical across both CLIs; the restore helper is byte-identical. Only the
  per-signal callback differs (Probe = single-shot shutdown; Sender = first cancels,
  second terminates with exit code 130).
- **Config leaf validators** — `port` (1..65535), `max_pdu` (1..16,777,215),
  `log_format` (`text`/`json`), and AE-title (ASCII, 1..16 bytes) checks are duplicated
  verbatim.
- **UID validation** — both enforce the same DICOM rule (dotted-decimal, ≤64 chars) but
  via two different implementations (Probe uses `re`; Sender uses pydicom's `UID`).

This ADR authorizes extracting those overlaps into a single shared Python package,
`lumora_lite_common`, and supersedes the contrary guidance in
`docs/sender_lite/IMPLEMENTATION_PLAN.md` §14.1, §23, and the `src/sender_lite/log.py`
docstring.

It does **not** alter PRD §1.2 / §TC-01: the Lite codebase still shares no source code
with the parent `lumora/` project. `lumora_lite_common` is internal to the Lite tools.

## Decision

Introduce a `lumora_lite_common` package, shipped in the existing single wheel alongside
`probe_lite` and `sender_lite`. It exposes four modules:

- `lumora_lite_common.logging` — an `EventLogger` base class holding the shared engine;
  `ProbeLogger` and `SenderLogger` become subclasses that override only the label map.
- `lumora_lite_common.signals` — `install_signal_handlers` / `restore_signal_handlers`
  as plain functions, parameterized by a caller-supplied per-signal callback.
- `lumora_lite_common.config_validators` — `validate_port`, `validate_max_pdu`,
  `validate_log_format`, and `validate_ae_title` as plain functions.
- `lumora_lite_common.uids` — `validate_uid`, `safe_uid`, and `is_valid_uid` as plain
  functions.

### Pragmatic OOP boundary

The shared package uses object orientation **only** where there is genuine shared state
plus real polymorphism — the logger. Everything else is plain functions, because wrapping
a stateless validator or a two-step signal install/restore in a class would add ceremony
for no benefit. Abstract base classes, protocols, plugin factories, and similar
abstractions are deliberately avoided.

### What stays per-package (not extracted)

- `__main__.py` — inherently per-package (each imports its own package); ~7 lines of
  net-shareable shim is not worth a bootstrap-time import.
- Config source/precedence engines — Probe uses environment variables; Sender uses TOML.
  These are genuinely different and remain separate.
- Catalog, sender transport, SCP/DIMSE handlers, and storage writes — correctly
  per-package with no overlap.

## Consequences

The four duplicated behaviors collapse into one tested, importable location; a change to
the logger format or a validator rule now happens once. Public class names
(`SenderLogger`, `ProbeLogger`) and existing test imports are preserved via thin
subclasses, so this is backward compatible. The Lite tools gain one internal dependency
(`lumora_lite_common`) but remain decoupled from the future parent `lumora/` project,
preserving PRD §1.2 / §TC-01. If the parent project later wants to reuse any of these
helpers, `lumora_lite_common` can be split into its own installable distribution with a
~10-line packaging change.
