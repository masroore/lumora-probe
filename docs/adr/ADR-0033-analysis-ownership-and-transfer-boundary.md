# ADR-0033: Analysis Ownership and the Transfer Analysis Boundary

- **Status:** Accepted
- **Date:** 2026-07-30

## Context

The baseline assigns per-leg transfer measurements and recommendations to "Transfer Analysis"
(`05` §12), while ADR-0018 assigns inferred explanations to a separate rule engine whose
findings live under `analysis/`. The distinction is architectural, not cosmetic: putting rules
inside the transfer measurement path would make inferred claims look like observed evidence and
would make rule-version changes alter capture contents.

The Phase 14 plan names this decision ADR-0028. The repository already uses ADR-0028 for the
Lite shared-common library, so this decision is recorded as ADR-0033 rather than silently
reusing an existing identifier.

## Decision

### Ownership

- **Associations/networking and capture slices** own observed evidence and mechanical transfer
  measurements: association state, per-leg timestamps, bytes, PDU sizes, presentation contexts,
  transfer syntaxes, receive/decode durations, status codes, and retry/timeout observations.
  They publish the existing event and protocol-trace contracts. They do not infer causes or
  recommend remediation.
- **The `analysis` slice** owns the condition registry, deterministic condition detection,
  rule-set registry, finding evaluation, confidence, explanations, next steps, evidence
  citations, and `analysis/` persistence. It consumes capture evidence through public contracts
  and events; it does not reach into another slice's repositories or domains.
- **The `web` slice** is composition and presentation only. It may request analysis results and
  render citations, but it contains no diagnostic rules and never writes findings.
- **The `reports` slice** consumes evidence and analysis outputs. Report generation does not run
  rules or mutate findings.
- **Plugins** contribute analyzers and rule metadata through the public plugin contracts. They
  use the same finding model, confidence vocabulary, rule versioning, and evidence-citation
  requirements as bundled rules.

### Boundary

Transfer Analysis is the **measurement boundary**, not a second inference engine. A transfer
measurement may expose facts such as per-leg latency, throughput, compression, or a transfer
syntax mismatch. A diagnostic condition is emitted only when the condition is mechanically
established from observed evidence and carries a stable condition ID. A finding is produced by a
versioned analysis rule and must include:

- rule ID and rule-set version;
- coarse confidence: `certain`, `likely`, or `possible`;
- cited event `sequence` values;
- plain-language explanation; and
- concrete next steps.

Findings are regenerable artifacts under the capture's `analysis/` directory. They are never
written to `events.jsonl`, never alter the captured evidence, and never become authoritative for
replay or projection rebuilds. Client-asserted events remain excluded from analysis and timing
per ADR-0016.

### Dependency direction

```text
associations / captures  -> observed events and measurements
analysis                 -> public evidence contracts + event stream
reports                  -> captures + analysis DTOs
web                      -> public contracts + application composition
plugins                  -> public analysis/plugin contracts
```

The `analysis` slice may depend on `core`, `shared`, and contracts from upstream slices only.
No upstream slice imports `analysis`; no `domain.py` imports web frameworks or persistence
frameworks. Cross-slice composition belongs in `web/` or an application bootstrap module.

## Consequences

- Transfer Inspector and future performance views can expose measured per-leg evidence without
  accidentally asserting why a transfer was slow.
- Rule-set upgrades can produce different findings against unchanged captures while preserving
  byte-for-byte evidence and event ordering.
- Deleting `analysis/` and rerunning analysis is safe and must reproduce the same findings for the
  same capture and rule-set version.
- Analysis tests must prove that no finding is appended to `events.jsonl`, every citation resolves
  to a real event sequence, and client-asserted events contribute neither findings nor timing.
- The Phase 14 condition registry and rule engine may now proceed; seed rules must not be written
  before this boundary is implemented.

## References

`01` §6 and §3 · `05` §12 and §22 · `06` Appendix A · ADR-0004 · ADR-0016 · ADR-0017 ·
ADR-0018 · ADR-0021 · ADR-0024 · `01-work-breakdown-structure.md` §C-14 ·
`02-phase-plan.md` §Phase 14
