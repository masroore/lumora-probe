# ADR-0019: Two Stream Endpoints — JSON for Consumers, HTML for the UI

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

A direct document conflict. `09` §8 mandates a structured envelope (type, timestamp,
correlation ID, payload, version) and §9 says WebSocket messages "should primarily
represent published domain events" — that is JSON. `09` §2 wants multiple concurrent
clients and `08` §2 makes the API canonical for UI, CLI, plugins and integrations.

But `04` §7 makes HTMX the primary interaction model, server-rendered, with "minimal
JavaScript" and an explicit "avoid large client-side application logic".

JSON on the socket means the browser must render it — a client-side rendering layer, and
every panel exists twice: a Jinja template for first paint and JavaScript for live
updates. HTML fragments make the socket UI-specific and leave `lumora watch` and
external integrations with nothing to consume.

## Decision

**Two endpoints over one source.**

- `/api/v1/events/stream` — canonical JSON envelopes for CLI, plugins and integrations.
  `09` §6/§7's topic subscription model applies here.
- `/ws/ui` — server-rendered HTML fragments for HTMX. Explicitly a presentation adapter
  in `web/`, not part of the API contract.

Both are fed by the same bus subscription through the same coalescing layer.

The deciding factor: **one set of Jinja partials serves both first paint and live
updates**. One template per panel, rendered by the HTTP handler initially and by the WS
adapter on change. That is the only arrangement in which `04` §7's minimal-JavaScript
constraint survives a live-updating UI, and it falls out of ADR-0012's slice rules — the
adapter lives in `web/`, no slice imports it.

**A coalescing governor sits between the bus and both endpoints, and is not optional.**
ADR-0014 bounded volume to ~5,000 domain events per 500-instance study, but they arrive
in bursts; one message per event destroys `02` §22's 100 ms budget. Fixed-interval flush
(~100 ms, configurable) with per-target policies: counters aggregate, status rows are
latest-wins, timeline appends with a cap. This is where ADR-0002's drop-oldest and
`EventsDropped` land, and ADR-0017's gap-free sequence makes any drop **provable** rather
than asserted. The JSON stream uses the same governor with a larger buffer, since `09`
§12 asks for backpressure on both.

**Fragments are targeted**, using out-of-band swaps addressed to specific DOM regions, so
only changed panels re-render (`15` §16).

**UI subscriptions are by mounted view**, not topic: the client declares which page and
panels are open and receives fragments only for those. Otherwise a background tab renders
HTML for every event in the system.

**The viewer is the deliberate exception.** Window/level, zoom, pan and cine are
Alpine/Cornerstone local state with no round trip — permitted by `04` §7's "small
interactive behaviors" and required by ADR-0015's decode/render split.

## Consequences

- HTML fan-out costs server CPU per client. Mitigated by rendering once per flush per
  distinct view-state and sharing the result; `15` §15's desktop-scale client counts make
  this a non-issue.

## References

`02` §22 · `04` §7 · `08` §2 · `09` §2, §6, §7, §8, §9, §12 · `15` §15, §16 · ADR-0002 ·
ADR-0012 · ADR-0014 · ADR-0015 · ADR-0017
