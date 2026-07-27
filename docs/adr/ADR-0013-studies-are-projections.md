# ADR-0013: Study / Series / Instance Are Projections Over Captures

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

`07` §4 lists `Study` as a top-level aggregate, a **sibling** of `Capture`. `07` §10's
tree reinforces it: `Study → Series → Instance` stands alone while `Capture → Events /
Logs / Analysis` sits separately, with Instance nowhere under Capture. `08` §6 exposes
`/studies`, `/series`, `/instances` as standing resources and `02` §10 gives the Study
Browser bookmarks. That describes a persistent global study library.

Against it: Charter §6 and `04` §6 both say the product will not become a PACS archive.
And ADR-0004 already made captures the permanent record, objects content-addressed
inside them, and the database a rebuildable index.

## Problem Statement

If Study is an independent aggregate with its own durable object store, the database
stops being rebuildable — it becomes a second source of truth — and ADR-0008's PHI
containment collapses, because deleting a capture no longer removes the pixels. `07`
§11 also requires every entity to have one owning aggregate, and the bytes physically
live in a capture's `objects/`.

## Decision

Study, Series and Instance are a **derived projection** over capture contents. Rows are
index entries rebuilt from capture manifests. Identity is the DICOM UID, so a study may
span captures and the browser shows the union with **per-instance provenance**.
Deleting a capture removes its instances from the view.

**A study spanning captures never renders as whole.** The browser shows "present in 3
captures", marks the study `partial`, and never implies completeness. `01` §3's
"Incomplete studies / Missing instances" is the *problem the user is investigating* — a
UI that silently unions fragments into something that looks complete hides the bug they
came for.

**Two different byte sequences under one SOP Instance UID is a first-class finding.**
Content addressing surfaces it for free. That is a real interoperability defect —
re-send with altered metadata, vendor UID reuse — that most tools silently overwrite.
Reported with both digests and both provenances (`01` §6).

**Ring-buffer-backed studies are expiring, and the UI says so.** Instances visible only
via the buffer vanish when the window rolls, so the browser shows retention state and
offers inline promotion. Bookmarks therefore reference capture-scoped instances, not
free-floating studies.

**Offline folder import creates a synthetic capture** rather than bypassing captures.
It gets `fidelity: objects` in its manifest, so protocol replay correctly refuses it —
there were never protocol events to replay. One ingest path, one ownership rule.

## Alternatives Considered

- **First-class durable studies.** Rejected: a de facto PACS archive, forbidden by
  Charter §6 and `04` §6, and it breaks the rebuildable-index invariant.
- **Derived by default plus a pinnable permanent library.** Rejected as the previous
  option in disguise: a pinned library means retention, dedup and deletion semantics of
  its own.

## References

`00` §6 · `01` §3, §6 · `04` §6 · `07` §4, §10, §11 · `08` §6 · ADR-0004 · ADR-0008
