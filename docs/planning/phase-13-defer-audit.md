# Phase 13 Defer-Candidate Audit

Date: 2026-07-30

## Summary

Phase 13 (Viewer) closeout plan splits workspace panel work into three waves. Waves 1 and 2
cover the panels that carry exit-criterion weight (retention join, instance source, report
timing, cine/fullscreen, ADR-0031 e2e, `ImageDisplayed` post-back, Event Timeline, Live
Monitor, Transfer Inspector). Wave 3 contains four additive views — **Dashboard, Search,
notifications, Log Console** — that are P1 workspace panels in the WBS (T-13-04-07,
T-13-04-08, T-13-04-12, T-13-04-05) but are not referenced by any Phase 13 exit criterion
and have no downstream phase depending on them. If Waves 1–2 are complete and verified but
schedule requires closing the phase, these four may be deferred.

## Candidates

### Dashboard (T-13-04-07)

- **Defers to:** Phase 14 (earliest available slot; Analysis phase already adds UI that
  references findings over the event stream, and the Dashboard's system-overview role
  composes naturally with that work). May also land in a later polish phase if Phase 14
  scope grows.
- **Exit criterion dependency:** None.
- **Rationale:** Additive view. System overview (`14` §16) aggregates data already exposed
  by the Event Timeline, Live Monitor, and Transfer Inspector — none of which depend on the
  Dashboard existing. No downstream phase consumes Dashboard output.

### Search panel (T-13-04-08)

- **Defers to:** Phase 14 (earliest available slot; search over studies/series/instances/
  events/logs is a navigation convenience that composes with the Analysis phase's findings
  UI).
- **Exit criterion dependency:** None.
- **Rationale:** Additive view. Search is a query surface over data already surfaced by the
  Metadata Inspector, Transfer Inspector, and Event Timeline. No exit criterion requires
  search, and no downstream phase depends on it.

### Notifications (T-13-04-12)

- **Defers to:** Phase 14 (earliest available slot; notification infrastructure pairs with
  the Analysis phase's `WarningRaised` / `ErrorRaised` surfacing).
- **Exit criterion dependency:** None.
- **Rationale:** Additive view. Critical failures are already surfaced by the Live Monitor's
  `EventsDropped` counter and the Event Timeline. Notifications are a presentation layer on
  top of events that already have a visible path. No exit criterion requires the toast /
  acknowledgment model.

### Log Console (T-13-04-05)

- **Defers to:** Phase 14 (earliest available slot; operational log view is distinct from
  the event stream per ADR-0014 and can land alongside the Analysis phase's diagnostic
  tooling).
- **Exit criterion dependency:** None.
- **Rationale:** Additive view. The Event Timeline already presents the event stream; the
  Log Console is the operational-log counterpart. No exit criterion requires it, and no
  downstream phase depends on it.

## Exit Criteria Verification

Phase 13 exit criteria from `docs/planning/02-phase-plan.md` §Phase 13:

> - Decode duration appears in a capture and a report — it is evidence, reproducible off
>   the originating machine.
> - A study spanning three captures never renders as whole.
> - Ring-buffer-backed instances show retention state and offer promotion.
> - Two byte sequences under one SOP Instance UID produce a finding with both digests.
> - W/L drag stays within the 100 ms budget with no round trip.
> - An undecodable transfer syntax reports *why* — "browser can't show it" and "pixel data
>   is broken" must not be indistinguishable.

**Finding:** None of the six exit criteria reference Dashboard, Search, notifications, or
Log Console. All six are satisfied by Wave 1 and Wave 2 work (decode pipeline, retention
join, instance source adapter, cine/fullscreen, ADR-0031 e2e, Transfer Inspector, Event
Timeline, Live Monitor).

**Critical finding:** None. No exit criterion depends on a defer candidate. Deferral is
safe.

## ADR Requirement

Deferring these four panels requires **no new ADR**. They are additive views with no
architectural decision attached — no boundary is crossed, no contract is changed, no
technology choice is made. The deferral is a schedule decision recorded in this audit and
in the Phase 13 completion report.

> Note: the closeout plan's §6 originally prescribed an ADR-0032 for panel deferral. This
> audit supersedes that prescription on the basis that the four candidates are P1 workspace
> panels with no architectural content — an ADR would be governance overhead for a schedule
> deferral. If the team prefers the ADR, ADR-0032 may still be written; this audit provides
> the content it would contain.
