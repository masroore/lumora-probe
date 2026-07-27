# ADR-0021: Plugins Are Trusted In-Process Code; the Manifest Is Disclosure

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

`10` §13 wants capability restrictions, permission checks and least privilege. `12` §11
says plugins should declare capabilities, request only required permissions, operate
within boundaries, avoid unrestricted access to core services, and be validated before
activation. `10` §4 says plugins should fail independently.

But `04` §10 fixes pluggy, which is in-process hook dispatch. Once a plugin module is
imported into our interpreter it has everything our process has: filesystem, network, the
data directory, `sys.modules`, and the ability to monkeypatch any core service. CPython
offers no mechanism to restrict that in-process. A manifest `capabilities` list is a
declaration of intent; nothing checks it at runtime, and nothing can.

## Decision

**Documented full trust.** Plugins are trusted code, as pytest plugins are. The manifest
declares capabilities for **disclosure and consent, explicitly not enforcement**.
Plugins ship disabled, installation is a deliberate act, and the UI states plainly that an
enabled plugin can do anything the Lumora process can do.

A UI showing "this plugin has permission to: read captures" would imply enforcement that
does not exist, which is worse than saying nothing.

**What is actually delivered toward `10` §4 and `12` §11:**

- **Exception containment at every hook boundary.** A raising plugin never propagates into
  core; it emits `ErrorRaised` with the plugin ID and is disabled after repeated failures.
  That is real failure isolation.
- **Time budget per hook**, reusing ADR-0002's per-subscriber budget: a slow plugin gets a
  warning event and, on repeat, auto-disable. Honest caveat: we can *measure* and
  *disable*, we cannot *interrupt*. An infinite loop stalls the event loop, and no
  in-process design fixes that.
- **Per-plugin health, metrics and version** surfaced (`14` §15), so "the tool got slow"
  resolves to a named plugin.
- **SDK compatibility gate**: a plugin declaring an incompatible SDK major is refused at
  load rather than crashing mid-hook (`10` §12).
- **Load-time structural validation**: manifest schema, SDK range, entry points, declared
  hooks exist. That is `12` §11's "validate before activation" honestly scoped —
  structural, not behavioural.
- **Plugins see `contracts.py` DTOs only** (ADR-0006, ADR-0012).

**Plugin installation is not an API operation in v1.** With no authentication on loopback
(ADR-0009), an endpoint that installs a Python package is arbitrary code execution
reachable by any local process or any page clearing ADR-0010's Host check. Installation is
filesystem placement plus a CLI command, requiring a restart. The API and UI may list,
enable, disable and inspect — never install. Enabling runs code, so enable is also
restart-scoped. When authentication arrives, API installation becomes defensible and gets
its own ADR.

**The seed rule set ships as bundled plugins on the public SDK**, not as privileged core
code. If the first-party analyzers cannot be written against the public extension points,
the extension points are wrong — and this is the cheapest way to discover that in Phase 17
rather than when a vendor tries it.

## Alternatives Considered

- **Subprocess isolation with enforced capabilities.** Delivers `10` §13 literally, at the
  cost of a hand-rolled IPC transport (excluded by `04` §13), pluggy demoted to a
  registry, ADR-0007's single-process model broken, and plugin authors losing direct
  access to the objects they analyze. The enforcement seam is placed so this can be added
  per-plugin later without moving anything.
- **Two tiers, in-process for first-party and subprocess for third-party.** Rejected: the
  boundary is decided by who wrote the code, which is not a security property.

## References

`04` §10, §13 · `10` §4, §12, §13 · `12` §11 · `14` §15 · ADR-0002 · ADR-0006 ·
ADR-0009 · ADR-0010 · ADR-0012 · ADR-0018
