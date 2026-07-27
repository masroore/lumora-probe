# ADR-0026: Honest Partial Redaction; Object-Dropping Is the Default Handover

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

The flagship workflow in `01` §8 and `02` §3 is: a vendor support engineer captures at a
customer site and hands the evidence to the vendor. Every decision so far makes that
artifact *complete* — content-addressed pixel data, full metadata, protocol traces. So it
is a PHI package leaving a hospital, and `12` §17 names HIPAA and GDPR.

`07` §21 and `12` §9 both require redaction and export protection. Neither says what it is.

## Problem Statement

Real de-identification is not a tag filter. PS3.15 Annex E covers several hundred
attributes; UIDs need consistent remapping or the Study/Series/Instance hierarchy breaks
(ADR-0013 made the whole browser UID-keyed); private tags are vendor-specific by
definition; structured reports embed names in text; and **burned-in annotation cannot be
removed by metadata processing at all** — secondary capture, ultrasound and screenshots
routinely carry the patient name in pixels.

## Decision

**Honest partial redaction, plus a safe default export.**

- Tag-level redaction against a configurable profile, with consistent UID remapping. Output
  is a **new** capture whose manifest records the source capture ID and the profile applied,
  preserving ADR-0004's immutability.
- Called **"redact"** — never "anonymize" or "de-identified" — with **no claim of PS3.15
  conformance**.
- Anything we cannot verify is flagged rather than silently passed: `BurnedInAnnotation`,
  Secondary Capture / US / screenshot SOP classes, unrecognized private tags and free-text
  fields all raise explicit warnings on the redacted output.
- **Object-dropping is the default handover format.** Export at `fidelity: events` ships
  events, protocol traces and a whitelisted metadata subset with no pixel data.

Making the safe export the default and the pixel-bearing export a deliberate opt-in inverts
the risk in the right direction, and it costs nothing to build: ADR-0014's stream separation
and ADR-0005's `fidelity` field already carve the capture along exactly that line. Most of
what this tool diagnoses — rejected associations, presentation context mismatches, transfer
syntax negotiation, timeouts, per-leg latency — lives entirely in the protocol layer and
needs no pixels.

## Alternatives Considered

- **No redaction in v1**, documenting that `.lpcap` contains PHI. Defensible and honest, but
  leaves the flagship workflow with no product support, which pushes engineers toward
  emailing raw captures anyway.
- **Full PS3.15 de-identification.** Rejected as the dangerous option: a button labelled
  "de-identify" that leaves a patient name burned into an ultrasound frame is worse than no
  button, because the engineer ships it believing it is clean and we induced that belief.

## Consequences

- Full PS3.15 profile support becomes a later ADR and a plausible **plugin** (`10` §5 lists
  exporters), where a vendor or hospital supplies a profile they are willing to certify.
  That is the right home for a compliance claim, since it is not one we can make on their
  behalf.

## References

`01` §8 · `02` §3 · `07` §21 · `10` §5 · `12` §9, §17 · ADR-0004 · ADR-0005 · ADR-0013 ·
ADR-0014
