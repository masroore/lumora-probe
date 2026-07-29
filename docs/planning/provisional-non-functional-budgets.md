# Provisional Non-Functional Budgets

**Task:** T-03-03-02
**Status:** Provisional — ratification scheduled for Phase 11
**Date:** 2026-07-29

These budgets convert the only quantified capacity figures in ADR-0014 and the approved
UI target into checks that can fail. They are not release commitments until ratified
against representative traffic in Phase 11.

| Area | Provisional budget | Basis | Measurement |
| --- | --- | --- | --- |
| Domain event volume | At most 10 domain events per instance on average; at most 5,000 for a 500-instance study | ADR-0014's 6–10 events per instance and ~5,000-study example | Count `events.jsonl` domain records per completed study |
| Protocol trace volume | Plan for approximately 16,000 PDU records for a 500-instance study at the default 16 KiB PDU size | ADR-0014's 512 KiB instance / ~32 PDUs and ~16,000-study example | Count compact `pdus.jsonl` records and compare against instance byte totals |
| Always-on ring buffer | 30 minutes of recent evidence, capped at 2 GiB | ADR-0008 and ADR-0014 | Measure retained bytes and oldest retained event age under sustained synthetic traffic |
| UI responsiveness | Under 100 ms for an ordinary UI interaction | Approved planning baseline cited by F-06 | Browser timing test in the viewer/API phase |

## Guardrail interpretation

- Domain events and protocol trace records remain separate streams. PDU volume must not
  be “fixed” by publishing PDU envelopes onto the event bus.
- A budget breach is observable test evidence, not permission to silently drop durable
  capture data.
- UI, capture, and replay measurements must identify workload and what was not verified.

## Ratification work

Phase 11 will replay representative synthetic studies, measure the budgets under the
approved concurrency model, and either ratify these values or record an ADR amendment.
Until then, tests and dashboards should label these thresholds `provisional`.
