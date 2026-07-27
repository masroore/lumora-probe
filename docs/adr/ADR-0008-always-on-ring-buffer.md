# ADR-0008: Always-On Ring Buffer Plus Promotable Capture Sessions

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

The baseline affirms two incompatible things. `05` §7 makes Capture Engine a discrete
user-started session publishing `CaptureStarted`/`CaptureCompleted`, and `07` §12 gives
it `Created → Running → Stopping → Completed → Archived` — a recording you press a
button to begin.

But `01` §4 says "Capture **every** important event", `01` §5 says every image,
metadata object, DIMSE command, log entry, timing sample and warning is an event that
can be inspected and replayed, `05` §7 also has Capture Engine consuming "**all**
observable events", and `08` §6 exposes `/events` as a standing resource.

## Problem Statement

Is traffic recorded only inside an explicit session, or always? Sessions-only loses the
association that happened twenty minutes ago — the failure mode that kills tools in
this category. Always-permanent means unbounded disk growth and PHI with no owner.

## Decision

**Both.** Everything is continuously recorded into a bounded rolling ring buffer, and
explicit captures remain first-class and unbounded. A user can **retroactively promote**
a window out of the buffer into a permanent `.lpcap` — "save the last 10 minutes",
"save this association".

This resolves the contradiction rather than picking a winner, and retroactive promotion
is implicit in `00` §3's own framing ("What happened during this association?" — past
tense, unprompted). The DevTools analogue the baseline keeps invoking works this way.

**Two lifecycles.** The ring buffer is a *service* with retention. A Capture is an
*aggregate* with `07` §12's state machine. Promotion creates a Capture whose manifest
records that it was promoted from the buffer over a specific time range.

**Mid-association truncation is explicit.** A promoted window routinely starts after
`AssociationStarted`. The manifest carries `partial: true` plus which aggregates are
incomplete, and protocol replay (ADR-0005) refuses a capture whose negotiation was
never recorded rather than replaying half a conversation.

**Defaults are a PHI tradeoff, stated deliberately.** The ring buffer ships
**enabled** with a conservative cap (30 minutes / 2 GB, both configurable) and objects
retained, plus a documented switch to events-only for sites that cannot have PHI on
disk unprompted. Enabled-by-default is chosen because a disabled buffer is a feature
nobody discovers until after they needed it. This is a considered deviation from
`12` §15's secure-by-default, not an oversight.

## Alternatives Considered

- **Explicit sessions only.** Rejected: contradicts `01` §4 and loses the evidence
  nobody knew to start recording.
- **Always-on and permanent with retention pruning.** Rejected: unbounded PHI
  accumulation with no owner.

## Consequences

- Promotion is a copy-and-seal of a time slice; ADR-0004's content-addressed objects
  make it a digest copy rather than a re-scan.
- Instances visible only via the buffer expire. The UI must show retention state and
  offer inline promotion (ADR-0013).

## References

`00` §3 · `01` §4, §5 · `05` §5, §7 · `07` §12 · `08` §6 · `12` §15
