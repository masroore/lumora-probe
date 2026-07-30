# Phase 13 Task Report — T-13-03-05 retention state in browser

**Status:** Partial

The existing capture API exposes ring-buffer retention state and now exposes an injected promotion
endpoint at `POST /api/v1/captures/ring-buffer/promote`. Binding instance retention metadata and an
inline promotion control into the study workspace remains outstanding.
