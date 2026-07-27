# ADR-0024: The Relay Is Service-Agnostic; Understanding Is Additive

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

ADR-0003 described the proxy as "accept downstream, open upstream, relay". That works for
C-STORE and not for C-MOVE, yet `06` Appendix A lists `CMoveRequested` and `CGetRequested`
in the core catalog as though it does.

In C-MOVE the requester names a **destination AE title**, and the PACS resolves that title
to a host and port from its own configuration and opens a **new association** to it. Probe
is not on that path: we relay the C-MOVE-RQ and see the progress responses
(remaining/completed/failed/warning counts), but the C-STORE sub-operations flow PACS →
destination and never touch us. C-GET is the opposite and relays fine — data returns on
the same association — provided SCP/SCU role selection is negotiated, itself a classic
interop bug worth recording verbatim.

## Decision

**The relay is service-agnostic; our understanding is additive.**

- Relay operates at the DIMSE/PDU level **generically**. Any command not recognized is
  passed through byte-faithfully, recorded structurally (command field, message ID,
  affected SOP class, dataset presence, timings) and surfaced as
  `UnrecognizedDimseObserved` — never aborted.
- Per-service **enrichment** — parsed fields, domain events, analysis rules — ships for
  C-ECHO, C-STORE, C-FIND and C-GET in v1.
- C-MOVE is relayed with its progress responses recorded, plus an explicit finding stating
  that sub-operation data flows out-of-band and naming what to reconfigure to see it.
- **Destination-AE interception is available as an explicitly configured mode**: Probe
  registers as the destination AE and store-forwards to the true destination. This is not
  new machinery — it is ADR-0003's endpoint foundation — but it is a labelled deployment
  topology with its own documentation, never something that appears to happen
  automatically.

MPPS (`N-CREATE`/`N-SET`), Storage Commitment (`N-ACTION`/`N-EVENT-REPORT`) and
vendor-private services pass through and are recorded structurally without being modelled.
Probe can therefore be dropped in front of traffic it has never seen and remain *useful*
rather than *destructive*, and DIMSE-N support becomes a later enrichment ADR rather than a
protocol rewrite. ADR-0014's `pdus.jsonl` is the substrate that makes unrecognized traffic
analyzable after the fact.

**Consequences:**

1. **"Unsupported" never means "silently degraded".** A relayed C-MOVE produces a finding
   (ADR-0018) explaining that Probe observed the command and counts but not the objects,
   with concrete remediation: point the requester's destination AE at Probe, or use C-GET.
   `01` §6 applied to our own blind spots.
2. **ADR-0003's pass-through negotiation is load-bearing here.** Because we mirror
   upstream's accepted presentation contexts downstream, we never need to know what an
   abstract syntax *means* in order to negotiate it correctly.
3. **Relay must not silently repair malformed traffic.** A naive parse-and-re-encode would
   normalize non-conformant data and hide the defect, destroying the evidence the user came
   for. Datasets relay byte-faithfully, conformance problems are recorded as diagnostic
   conditions, and anywhere we cannot relay faithfully is reported rather than fixed.

## Alternatives Considered

- **C-ECHO and C-STORE only, everything else rejected.** Safe, and makes Probe a device
  that breaks any workflow it does not recognize — the opposite of an observability tool.

## References

`01` §6 · `06` Appendix A · ADR-0003 · ADR-0014 · ADR-0018
