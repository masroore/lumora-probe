# Extension Point Gap Report — Phase 16

**Status:** Accepted for Phase 16 closeout

The eight Phase 14 seed rule families were ported to `lumora_probe.plugins.bundled_rules`.
The port uses only `lumora_probe.plugins.api` and `lumora_probe.plugins.contracts` DTOs. The
analysis slice consumes the same public `FindingDTO` shape through
`RuleEngine.evaluate_plugin`, so no aggregate or repository was exposed to the plugin.

| Seed family | Public hook | Result |
|---|---|---|
| Rejected association | `analyze` | Expressed without privileged access |
| No acceptable presentation context | `analyze` | Expressed without privileged access |
| Transfer syntax mismatch | `analyze` | Expressed without privileged access |
| Slow C-STORE | `analyze` | Expressed without privileged access |
| Incomplete study | `analyze` | Expressed without privileged access |
| Timeout and retry | `analyze` | Expressed without privileged access |
| Oversized dataset | `analyze` | Expressed without privileged access |
| C-MOVE out-of-band | `analyze` | Expressed without privileged access |

**Gap:** None found for the Phase 14 seed set.

**Boundary retained:** Plugins do not receive analysis aggregates, capture repositories,
private event-bus internals, or an installation API. Future extension needs must add a
versioned public DTO/hook or be recorded as a new gap; no privileged workaround is allowed.
