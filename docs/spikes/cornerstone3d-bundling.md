# Cornerstone3D Bundling Spike

**Phase:** 04 — Core Infrastructure  
**Decision:** Pass — bundle the rendering path only.

## Question

Can Lumora Probe ship a local Cornerstone3D browser bundle without moving DICOM parsing or
codec execution into the browser?

## Result

`assets/source/cornerstone-renderer.js` imports only `@cornerstonejs/core` rendering APIs and
is bundled as `static/js/cornerstone-renderer.js` with esbuild. The entry point exports the
rendering engine and viewport primitives required by the future custom decoded-frame image
loader.

The bundle does **not** import a DICOM parser, a DICOM data-loader package, or a WASM codec.
The server remains responsible for decode and frame delivery per ADR-0015.

## Reproduction

```sh
npm ci
npm run build:assets
```

The build writes deterministic committed CSS, the Cornerstone rendering bundle, and vendored
single-file libraries under `assets/vendor/`. CI runs the same build and fails if committed
outputs drift.

## Constraints

- Node is required only when changing frontend dependencies or source assets.
- Runtime installation and Python-only changes do not require Node.
- All browser assets are local; no CDN or runtime network fetch is used.
- Dependency versions and licenses are recorded in `assets/vendor/manifest.json`.
