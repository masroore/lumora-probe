# ADR-0005: Replay Has Three Meanings; Two Ship in v1

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

The baseline uses one word for three operations. `05` §8: "Load captures, Replay
timing, Recreate protocol activity." `06` §16: "Replay SHALL reconstruct behavior from
persisted events." `00` §3 and `02` §16: "Reproduce production issues."

This retroactively constrains ADR-0004. `events.jsonl` plus `objects/` records what
was observed, not necessarily enough to reproduce the wire. Retrofitting fidelity into
an immutable evidence format later makes every earlier capture unreplayable.

## Decision

Two modes ship in Phase 13:

- **Event replay** — offline, into the bus, no network. Re-emits persisted envelopes
  at original or scaled timing. Drives timeline, diagnostics, analysis re-runs and
  regression tests. Matches `06` §16 exactly. Needs nothing beyond ADR-0004.
- **Protocol replay** — Probe as SCU against a real target. Re-opens an association
  and re-sends captured datasets with original inter-message timing.

**Byte-exact / mock-peer replay is deferred** behind its own ADR. Its real value is
the mock-peer direction (Probe standing in as a recorded PACS so a developer can test
their SCU), not wire-level re-send: message IDs, negotiation responses and timing all
differ on replay, so "byte-exact against a live peer" is largely fiction and will not
be sold as one.

**Capture-side implications, decided now:**

- Capture always records PDU-level structure (type, length, PDV boundaries,
  presentation context IDs, per-PDU arrival timestamps). See ADR-0014 for where it
  lives.
- `manifest.json` carries a `fidelity` field naming which streams are present:
  `events` → `protocol` → `wire`. Raw wire bytes are opt-in.
- Replay **refuses** modes the capture cannot support and says what is missing.
  Silently degrading would let someone conclude "it worked on replay" from a replay
  that never sent anything — a `03` §12 violation.

**Replay provenance.** A replayed `CStoreReceived` is otherwise indistinguishable from
production evidence, and capturing while replaying is the normal debugging loop. Events
therefore carry additive `replay_id` and `replay_of_event_id` fields (permitted by
`06` §8), and a replay run gets a **fresh** `correlation_id` linked to the original.
Reusing the original would merge two investigations into one timeline.

**Protocol replay is a live write to a real system.** Dry-run is the default; the
target must be explicitly configured rather than inherited from the capture; C-STORE
replay against a target not on an allowlist is refused; every run is audit-logged per
`12` §10. The failure mode being guarded against is replaying a 900-instance capture
into production and creating 900 duplicate objects.

## Consequences

- Only one replay concurrently, and it is exclusive (ADR-0023).
- A promoted ring-buffer window whose negotiation was never recorded cannot be
  protocol-replayed; it is refused, not approximated (ADR-0008).

## References

`00` §3 · `02` §16 · `03` §12 · `05` §8 · `06` §8, §16 · `12` §10
