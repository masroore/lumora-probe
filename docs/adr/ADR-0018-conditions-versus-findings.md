# ADR-0018: Observed Conditions and Inferred Findings Are Physically Separate

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

`01` §6 ("Explain Everything") commits the product to never saying "Transfer Failed" and
instead reporting what, where, when, **why it likely happened**, and **what to
investigate next**. `05` §12 has Transfer Analysis publishing recommendations. `03` §12
requires errors to surface remediation guidance.

Nothing specifies where that knowledge comes from. And "why it likely happened" is
**inference**, not observation — in tension with the invariant protected since ADR-0004:
a `.lpcap` is trustworthy because everything in it was witnessed. ADR-0016 restricted
what a browser may write to the evidence stream; a rule engine writing "the PACS probably
rejected this because of a transfer syntax mismatch" into that same stream is a larger
version of the same problem — a guess wearing the clothes of a socket read.

## Decision

Two layers, physically separated.

- **Diagnostic conditions** — deterministic, observed, no inference. Stable IDs
  (`LP-NEG-004: no presentation context accepted for SOP class X`). These are facts and
  ride the event stream as `WarningRaised` / `ErrorRaised` with a `code` field, per `06`
  Appendix A.
- **Findings** — rule-derived inference. Each carries a rule ID and rule version, a
  confidence, the evidence it cites (event sequence numbers per ADR-0017), a
  plain-language explanation, and next steps. Findings live in `analysis/` inside the
  capture (ADR-0004), **never** in `events.jsonl`.

**Analysis is a pure function of (capture, rule-set version).** Consequences taken
seriously:

1. **A finding is never authoritative and never load-bearing.** Delete `analysis/`,
   re-run, get the same findings — or better ones from a newer rule set against evidence
   that never changed. That inverts how tools in this category age: their conclusions are
   normally baked in at capture time and cannot improve.
2. **Every finding cites sequence numbers**, and the UI links a claim to the events
   behind it, so a user can check the reasoning rather than trust it. This is `01` §6's
   "what to investigate next" made mechanical.
3. **Rule IDs are stable and versioned; reports record the rule-set version used.** Two
   engineers comparing reports from different Probe versions need to know whether a
   finding vanished because the traffic changed or because we changed our mind. It also
   gives users a code to look up, argue with and cite in a vendor ticket.
4. **Confidence is coarse and honest:** `certain` (deterministic — the condition *is* the
   finding, e.g. a rejection with a known result/source/reason triplet), `likely`,
   `possible`. No numeric scores; we have no calibration data and "73%" would be invented
   precision.
5. **Rules are declarative data where the shape allows, Python where it does not**, with
   explanation text alongside the rule — so a plugin-contributed analyzer (`05` §12, `10`
   §5) uses the identical structure rather than a second-class bolt-on. Vendor-specific
   diagnostics (Charter §5) are exactly this, and are why the plugin system exists.

The seed rule set follows `01` §3 directly, since that list is effectively its
specification: rejected associations, no acceptable presentation context, transfer syntax
mismatch, slow C-STORE with per-leg attribution (ADR-0003), incomplete studies, missing
instances, timeouts and retries, oversized datasets.

## Alternatives Considered

- **Facts only, no causal claims.** Honest, and abandons `01` §6 — the sentence the
  product vision rests on.
- **One stream with everything confidence-labelled.** Rejected: puts inference and
  observation in the same artifact where a `jq` consumer sees them as peers.

## References

`00` §5 · `01` §3, §6 · `03` §12 · `05` §12 · `06` Appendix A · `10` §5 · ADR-0004 ·
ADR-0016 · ADR-0017
