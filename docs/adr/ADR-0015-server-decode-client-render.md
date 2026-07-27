# ADR-0015: Server Decodes Pixels; Cornerstone3D Is Demoted to Renderer

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

`04` approves both halves of a decode stack and never says which runs: pylibjpeg with
pylibjpeg-openjpeg and optional GDCM server-side (§5), and Cornerstone3D client-side
(§7). Cornerstone3D ships its own WASM codecs and consumes DICOM P10 directly, so these
overlap almost entirely — against `04` §14's "avoid overlapping libraries".

## Decision

**The server decodes; the client renders.** The server decodes to normalized 16-bit
grayscale plus a small JSON sidecar (dimensions, rescale slope/intercept, suggested
window, photometric interpretation). Cornerstone3D is used as a *renderer* through a
custom image loader against our endpoint — **not** as a DICOM parser. Window/level,
zoom, pan, invert and cine stay client-side on the raw pixels.

Reasoning specific to this product:

- **Decode duration is a product feature.** `02` §13's Transfer Inspector displays it
  and `06`'s catalog has `ImageDecoded`. Decoded in the browser, that number is a
  property of the user's laptop, is not reproducible, and cannot appear in a shared
  capture or report. Server-side decode makes it evidence.
- **Codec coverage is the failure mode we exist to diagnose.** Exotic and proprietary
  transfer syntaxes are the bug, not the happy path, and Cornerstone's WASM codec set is
  narrower than pylibjpeg plus optional GDCM. With client decode, "the browser can't
  show it" and "the pixel data is broken" are indistinguishable — exactly the wrong
  ambiguity here.
- **The overlap resolves cleanly:** pylibjpeg decodes, Cornerstone3D renders.

**Implementation:** decoded frames in a server-side LRU cache; `02` §22's "current ±2
decoded" is honoured as a *prefetch* policy rather than a hard cap; frame endpoints are
per-instance-per-frame so multi-frame and cine stream rather than block; decode runs in
ADR-0002's executor, never on the loop.

## Alternatives Considered

- **Client decodes; serve raw DICOM.** Zero server CPU, but forfeits decode timing as
  evidence and narrows codec coverage.
- **Server decodes and re-encodes to PNG/JPEG.** Worst of both: 8-bit re-encoding
  discards the dynamic range window/level exists to explore, and puts a round trip in
  front of every W/L drag, breaking `02` §22's 100 ms target.

## Consequences

- Client-side viewer state is the deliberate exception to `04` §7's minimal-JavaScript
  rule (ADR-0019).
- The vendored Cornerstone artifact shrinks substantially, since only the rendering path
  is needed (ADR-0025).

## References

`02` §13, §22 · `04` §5, §7, §14 · `06` Appendix A · ADR-0002 · ADR-0019 · ADR-0025
