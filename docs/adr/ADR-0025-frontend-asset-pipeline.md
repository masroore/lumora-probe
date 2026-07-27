# ADR-0025: Node at Asset-Build Time Only; Built Assets Are Committed

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

`04` §7 approves Tailwind CSS 4 and Cornerstone3D; both are npm-native. Tailwind 4
compiles CSS by scanning source files for class names — there is no usable pre-built
"everything" stylesheet. Meanwhile the project is Python-only (uv + Hatchling, `04` §3),
`04` §14 says minimize dependencies, and ADR-0009's no-outbound-telemetry commitment rules
out CDN loading, so every asset must be vendored locally.

Most of the frontend is easy: HTMX, Alpine.js, Chart.js and Tabulator all ship single-file
dist builds that vendor directly with no build step, and Lucide icons can be inlined as SVG
by Jinja with no JavaScript at all. The problem is exactly two dependencies — Tailwind
(needs a compile) and Cornerstone3D (npm-distributed ESM with a dependency graph, not a
drop-in file).

## Decision

**Node at asset-build time only; compiled outputs committed.**

`package.json` and a lockfile exist and are used by whoever changes CSS or upgrades a JS
dependency. The compiled artifacts (`static/css/app.css`, the Cornerstone bundle) are
committed and shipped in the sdist and wheel. **Installing or running Lumora Probe never
requires Node; editing Python never requires Node.**

End users install via uv or Docker and must never need a JavaScript toolchain to run a
DICOM diagnostic tool. Committing build artifacts is usually a smell; here it is what makes
`uv pip install lumora-probe` self-sufficient and keeps the air-gapped hospital-network case
working, which ADR-0009 already committed us to.

**Specifics:**

1. **CI fails on stale assets.** A Python contributor adding `class="..."` to a Jinja
   template gets no style unless the CSS is recompiled, so CI rebuilds the assets and fails
   if the result differs from what is committed. Without that check the failure is invisible
   — the page just renders slightly wrong — which `03` §12 prohibits.
2. **ADR-0015 shrinks the Cornerstone problem.** Because the server decodes and Cornerstone
   is only a renderer fed by a custom image loader, we need its core rendering path, not its
   DICOM parser and not its WASM codec bundles. A Phase 04 spike confirms the bundling
   approach before committing.
3. **Asset provenance is recorded.** Vendored third-party files get versions and licenses
   listed in a manifest, per `04` §14's license review and `13` §13's dependency scanning —
   otherwise vendored JavaScript is an unauditable blind spot.

## Alternatives Considered

- **Full Node pipeline required for development.** This decision plus a prerequisite nobody
  needs.
- **No Node at all**, using the Tailwind standalone binary and whatever pre-built bundle
  Cornerstone3D publishes. Rejected: trades a controlled build step for an uncontrolled
  dependency on upstream packaging choices.

## References

`03` §12 · `04` §3, §7, §14 · `13` §13 · ADR-0009 · ADR-0015
