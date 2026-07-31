# Documentation Index

This index separates current operator/developer guidance from architectural authority and
historical planning evidence.

## Start here

- [Repository README](../README.md) — installation, quick starts, development gates, and
  product boundaries.
- [Operator guide](guides/operator-guide.md) — startup, configuration, data roots, health,
  shutdown, and backup.
- [Deployment topologies](guides/deployment-topologies.md) — standalone, reverse-proxy, and
  container boundaries.
- [Known limitations](guides/known-limitations.md) — release scope and explicit non-claims.
- [Troubleshooting](guides/troubleshooting.md) — common startup, readiness, storage, and
  replay failures.

## Lite utilities

- [Probe Lite](probe_lite/README.md) — C-STORE/C-ECHO receiver, storage layout, logging,
  configuration, status codes, and tests.
- [Sender Lite](sender_lite/README.md) — directory cataloging, Study Batches, association
  behavior, TOML configuration, logging, cancellation, and exit codes.
- [Lite product requirements](lumora-probe-lite-prd.md) — scope and requirements history.
- [Lite vocabulary](../CONTEXT.md) — Catalog, Study Batch, Study Association, and related
  terms.

## Architecture authority

1. [`adr/`](adr/) — accepted decisions and recorded deviations; authoritative when a decision
   conflicts with another document.
2. [`architecture-baseline/`](architecture-baseline/) — numbered product and architecture
   baseline.
3. [`generated/`](generated/) — checked-in OpenAPI, AsyncAPI, event-catalog, and condition-
   catalog artifacts generated from the implementation.

Important indexes:

- [ADR index](adr/README.md)
- [System architecture](architecture-baseline/03-system-architecture.md)
- [Technology stack](architecture-baseline/04-technology-stack.md)
- [System modules](architecture-baseline/05-system-modules.md)
- [Storage architecture](architecture-baseline/11-storage-architecture.md)
- [Security architecture](architecture-baseline/12-security-architecture.md)
- [Testing strategy](architecture-baseline/13-testing-strategy.md)
- [Glossary](architecture-baseline/19-glossary.md)
- [Plugin SDK](../docs/plugins/sdk.md)

## Guides

| Guide | Use it for |
| --- | --- |
| [Docker](guides/docker.md) | Build and run the non-root runtime image |
| [Operator guide](guides/operator-guide.md) | Configure and operate a server |
| [Deployment topologies](guides/deployment-topologies.md) | Choose a trusted network boundary |
| [User workflows](guides/user-workflows.md) | Capture, analysis, replay, and handover workflows |
| [Vendor handover](guides/vendor-handover.md) | Export and review investigation evidence |
| [Privacy and compliance posture](guides/privacy-and-compliance-posture.md) | Understand PHI and redaction limits |
| [Troubleshooting](guides/troubleshooting.md) | Diagnose operational failures |
| [Upgrade and migration](guides/upgrade-and-migration.md) | Upgrade release data and deployments |
| [Known limitations](guides/known-limitations.md) | Check deferred or unsupported capabilities |

## Release and planning evidence

- [Release notes for v0.1.0](release-notes/v0.1.0.md)
- [Changelog](../CHANGELOG.md)
- [`planning/`](planning/) — phase plans, completion reports, acceptance matrices, and GA
  sign-off evidence. These documents preserve historical decisions and timestamps; they are
  not a substitute for current guides.
- [`spikes/`](spikes/) and [`other/`](other/) — bounded investigations and superseded plans.

Historical planning documents may describe an earlier implementation state. For current
behavior, prefer source code, generated artifacts, ADRs, and the current guides above.
