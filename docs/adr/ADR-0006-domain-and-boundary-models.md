# ADR-0006: Plain-Python Domain, Pydantic at Boundaries

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

A direct document conflict. `03` §4 says the domain layer is "framework
independent"; `07` §3 says business concepts "SHALL not depend on persistence
technologies". `04` §4 lists Pydantic v2 as the tool for request validation, response
models, configuration **and domain validation**.

Pydantic is a framework. `04` puts it in the domain; `03` and `07` forbid exactly
that. Charter §12 ranks `03`/`07` above `04` on architecture but `04` above them on
technology selection, so the hierarchy does not resolve it.

Two constraints narrow the choice. SQLAlchemy Core with no ORM means a domain↔row
mapping layer is mandatory under every option, so that cost is not a differentiator.
And `08` §4 requires a stable `/api/v1` while `10` §12 requires SDK backward
compatibility — yet `07` §18 requires the domain model to evolve. One shared class
cannot be both frozen for consumers and free to change internally.

## Decision

**Two layers.**

- **Domain**: plain Python. Value objects are `@dataclass(frozen=True, slots=True)`
  with invariants checked in `__post_init__`. Aggregates are ordinary classes with
  behaviour and no external base class.
- **Boundaries**: Pydantic v2. REST and WebSocket schemas, configuration, the event
  envelope and its payload catalog, plugin manifests, capture manifests.
- Repositories own explicit, hand-written row↔domain mapping.

`04` §4's "domain validation" is read as *Pydantic is the approved validation library
where validation happens at a boundary*, not as a mandate that aggregates inherit
`BaseModel`. This reading is the deviation, recorded here rather than left silent.

**The event envelope is a wire contract**, so it is Pydantic, versioned per `06`
§6/§8, with a payload-model registry keyed by `(event_name, event_version)`. Unknown
fields are **preserved, not stripped** — `06` §3 requires tolerating future fields and
`06` §16 requires byte-faithful persistence, so the capture-write path keeps raw bytes
alongside the parsed model.

**Plugins see boundary types only**, never aggregates. Leaking an aggregate into a
plugin signature makes every internal refactor an ecosystem break.

## Alternatives Considered

- **One Pydantic model per concept, used everywhere.** Least code, rejected: renaming
  a domain field becomes a breaking API change and a breaking plugin change, forever.
  Domain invariant violations would also surface as `ValidationError`, leaking
  Pydantic's vocabulary into an engineering-facing error model that `03` §12 wants to
  carry remediation guidance.
- **Three layers, with separate persistence record types.** Rejected: with Core the
  persistence record is already a dict-like row, so a dedicated class is ceremony that
  `04` §14 and `18` §3 both argue against.

## Consequences

- Hand-written mappers. Accepted: explicit, greppable and type-checkable beats shared
  models that quietly couple five contracts (`18` §6, "explicit rather than implicit").
- Frozen dataclasses fit `07` §8's "immutable value objects where practical" and cost
  nothing per construction — relevant on the per-PDU hot path.

## References

`03` §4, §12 · `04` §4, §14 · `06` §3, §6, §8, §16 · `07` §3, §8, §18 · `08` §4 ·
`10` §12 · `18` §3, §6
