# ADR-0001: The Architecture Baseline Is Constitutional, Not a Blueprint

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

The project has 21 documents under `docs/architecture-baseline/`. Only
`06-event-driven-architecture.md` is normative: it uses RFC 2119 terms, defines a
concrete envelope, and names an event catalog. The others are largely checklists of
section headings:

- `07-data-model.md` §7 lists what each entity "should define", then defines no field
  of any entity; §23 defers eight open questions that together cover the entire
  storage layer.
- `11-storage-architecture.md` §6: "Physical schema is intentionally unspecified."
- `08-rest-api-specification.md` §5: authentication "remains implementation-specific."
- `10-plugin-sdk.md` §7: discovery "remains implementation-specific."

## Problem Statement

The build brief instructs: if architectural conflicts exist, stop and write a review
instead of coding. Read literally, work never starts — the gaps are the bulk of the
design surface, not incidental omissions.

## Decision

The baseline is **binding where it is specific and silent elsewhere**.

Binding invariants: the approved stack (`04`), the event envelope and compatibility
rules (`06`), headless / event-driven / API-first structure (`03`), the non-goals
(`00` §6, `01` §10), aggregate-oriented modelling (`07`), and module boundaries
(`05` §21, §24).

Everything the baseline leaves open is decided by ADR. A decision that *contradicts*
a specific baseline statement is permitted only via an ADR naming the document, the
section, and the reason. Silent deviation is prohibited.

## Alternatives Considered

- **Complete the documents to blueprint depth before writing code.** Rejected: turns
  a build into an indefinite documentation project, and specifications written with no
  running code behind them fail in ways nobody can detect until implementation.
- **Treat the documents as advisory.** Rejected: discards the one thing the baseline
  does well, which is fixing technology and structural invariants so they are not
  relitigated every phase.

## Consequences

- `docs/adr/` is the authoritative resolution layer, sitting below the PRD and above
  technical design in the Charter §12 hierarchy.
- Phase 01 delivers a compliance review and gap register, not a stop-the-line report.
- ADR-0002 … ADR-0026 accompany this record and resolve the foundational gaps.

## Risks

- ADR sprawl. Mitigated by one decision per record and superseding rather than
  rewriting (`17` §12).
- Discretion drifting from intent. Mitigated by requiring every ADR to cite the
  baseline sections it relies on or deviates from.

## References

`00` §12 · `03` · `04` · `06` · `07` §23 · `11` §6 · `17` §8
