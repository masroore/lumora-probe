# ADR-0003: Inline Proxy as Primary Observation Mode

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

The baseline points two directions. Toward *endpoint*: `04` §5 gives pynetdicom
association management, DIMSE messaging, SCP/SCU roles and negotiation — the
capabilities of a DICOM node. No packet-capture library appears anywhere in the
approved stack. Toward *observer*: `02` §2 says "Think Wireshark", and `00` §3 lists
"Why won't this scanner communicate with the PACS?" — a conversation between two
third parties that a terminating endpoint cannot witness.

## Problem Statement

Does Lumora Probe observe traffic by participating in it or by sniffing the wire?
These are different products with different dependency sets and privilege
requirements.

## Decision

**Inline proxy, built on an endpoint (SCP + SCU) foundation.** Probe accepts the
downstream association, opens its own association upstream, and relays — observing
both halves.

**Negotiation fidelity has two explicit modes:**

- *Pass-through* (default): open upstream first, mirror upstream's accepted
  presentation contexts back downstream. True fidelity; adds a round trip; fails when
  upstream is unavailable.
- *Permissive standalone capture*: accept everything downstream and negotiate
  upstream independently. Works without an upstream, but masks negotiation failures —
  precisely the bug class users are hunting. Never silent; always labelled in the UI
  and in the capture manifest.

**Association pairs are first-class.** In proxy mode there is no single association.
The data model represents the pair, and Transfer Analysis (`05` §12) attributes time
to the downstream leg, the Probe hop and the upstream leg **separately**. Reporting
these as end-to-end modality↔PACS timings would be a lie.

Passive packet capture is deferred: offline import of a third-party pcap becomes a
plugin behind its own ADR.

## Alternatives Considered

- **Endpoint only (store-and-forward).** Retained as the foundation and as the
  configured mode for destination-AE interception (ADR-0024), but insufficient alone:
  it cannot answer the Charter's headline interoperability question.
- **Passive packet capture.** Rejected for v1: pynetdicom exposes no standalone wire
  decoder suitable for passive stream reassembly, so this means a bespoke PDU/DIMSE
  decoder plus TCP reassembly plus a dependency outside `04` plus `CAP_NET_RAW` plus a
  SPAN port. It also fails entirely against TLS, which `12` §14 expects us to support
  and which a terminating proxy can observe.

## Consequences

- Probe is a participant, and the observer effect must be visible in the UI and the
  data model rather than hidden.
- TLS-protected conversations are observable because Probe terminates them.
- Deployment requires pointing the sender at Probe. This is a real adoption cost and
  is documented rather than engineered around.

## Risks

- Probe becomes a failure point in a live path. Mitigated by pass-through negotiation
  fidelity, byte-faithful relay (ADR-0024), and never silently repairing traffic.

## References

`00` §3, §5 · `01` §3 · `04` §5 · `05` §6, §12 · `12` §14
