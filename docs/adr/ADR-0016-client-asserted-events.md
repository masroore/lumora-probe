# ADR-0016: Client-Asserted Events Are Admitted and Quarantined at Format Level

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

`05` §10 has the Viewer publish `ImageDisplayed` and `06` Appendix A lists it. After
ADR-0015 the display happens in a browser, so the event can only exist if the browser
posts it back. Combined with ADR-0009 (no authentication) and ADR-0010 (loopback, no
CORS), that means any local process — and any page clearing the Host check — can write
into the evidence stream.

## Problem Statement

Does a capture contain assertions the server did not witness? The product's value is
that a `.lpcap` handed to a vendor is trustworthy.

## Decision

**Admitted, and quarantined at the format level rather than only in application code.**

- `origin` is a **required** envelope field on every event: `observed` |
  `client-asserted`. Absence is a validation error, not an assumed-trusted event.
  Additive to `06` §6, permitted by `06` §8.
- `manifest.json` declares whether the capture contains client-asserted events and how
  many, so a handover states it rather than burying it.
- Client-origin events are accepted only on a dedicated endpoint, with `producer` forced
  to `web-ui`, confined to the Viewer category, rate-limited and payload-validated.
- They render in the timeline — the correlation value is real: what the engineer was
  looking at when something failed. They are **never** inputs to Analysis, never
  contribute timing to Transfer Analysis, and are excluded from replay fidelity.

The format-level requirement is the substance of this decision. A consumer reading
`events.jsonl` with `jq` sees `AssociationStarted` and `ImageDisplayed` as peers; a
field that is only present sometimes helps only those who know to check. Making `origin`
mandatory on every event means the distinction cannot be missed.

## Alternatives Considered

- **Drop `ImageDisplayed` entirely**, keeping only server-observed `ImageRequested` and
  `ImageDecoded`. Structurally safer: everything in the stream was witnessed on a socket
  or in our own process. Rejected in favour of retaining timeline correlation value,
  with the format-level quarantine as the compensating control.
- **A separate telemetry sidecar outside the event catalog.** Rejected: a fourth stream,
  immediately after ADR-0014 argued against write amplification.

## Risks

- A local process poisoning the timeline. Bounded to the Viewer category, marked in
  every envelope, counted in the manifest, and excluded from all inference.

## References

`05` §10 · `06` §6, §8, Appendix A · ADR-0009 · ADR-0010 · ADR-0015
