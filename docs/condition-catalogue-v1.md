# Lumora Probe Condition Catalogue v1

Stable condition codes are allocated as `LP-XXX-NNN`:

- `XXX`: three uppercase letters naming the condition namespace.
- `NNN`: three-digit sequence from `001` through `999`.
- IDs are never reused, even when a condition is retired.
- Every condition is deterministic and observed; inferred explanations belong to findings under
  `analysis/` and never to `events.jsonl`.

| Code | Meaning | Remediation |
|---|---|---|
| `LP-NEG-001` | Association negotiation was rejected. | Compare rejection result, source, reason, and offered contexts with peer configuration. |
| `LP-NEG-002` | Association was aborted before normal release. | Inspect abort source and the last observed protocol events on both legs. |
| `LP-NEG-004` | No acceptable presentation context was observed. | Offer a context containing the SOP class and a transfer syntax accepted by the peer. |

Generated machine-readable artifact: `docs/generated/condition-catalog-v1.json`.
