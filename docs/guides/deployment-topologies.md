# Deployment Topologies

Lumora Probe is a single-process engineering observability service for DICOM traffic.
This guide distinguishes **implemented** topologies from conceptual future variants.

## Shared posture (all topologies)

- HTTP binds **loopback by default** (`127.0.0.1`).
- Non-loopback binds require explicit acknowledgment via `--trust-network`
  (`LUMORA_ALLOW_UNAUTHENTICATED_NETWORK`) per ADR-0010.
- v1 has **no authentication** (ADR-0009). Do not expose the process on a shared network
  without an external trust boundary.
- **TLS and authentication are reverse-proxy responsibilities.** Lumora Probe does not
  terminate TLS or provide RBAC in v1.
- The DICOM listener binds **11112** by default so it never needs root.

## 1. Standalone (implemented)

Operator runs `lumora serve` on a workstation or jump host. Capture, replay, analysis, and
the HTMX workspace share one process and one data root (`LUMORA_DATA_DIR`).

Use when investigating traffic on the same host that can reach the DICOM peers under test.

## 2. Inline reverse proxy (supported deployment pattern)

Place nginx, Caddy, or another reverse proxy in front of loopback-bound Lumora Probe:

1. Probe listens on `127.0.0.1:8000`.
2. Proxy terminates TLS and optionally adds authentication.
3. Operators reach the UI/API only through the proxy.

This is the recommended way to introduce TLS without changing Probe’s no-auth v1 surface.

## 3. Destination-AE interception (conceptual / operator-arranged)

Some investigations place Probe where a modality or workstation would otherwise open an
association to a PACS. Probe’s capture/replay surfaces support that workflow when the
operator configures AE titles and network routing outside the product.

Probe is **not** a transparent network tap and does not claim inline proxy fidelity beyond
what the capture engine records. Future observation topologies remain governed by ADR-0003.

## Explicit non-claims

- No built-in TLS
- No built-in authentication or RBAC
- No remote collector fleet (deferred)
- No claim that a reverse proxy alone satisfies clinical compliance obligations

See also: [operator-guide.md](operator-guide.md), [privacy-and-compliance-posture.md](privacy-and-compliance-posture.md).

## Docker image

The supported container contract is documented in [docker.md](docker.md): one writable
`/var/lib/lumora` volume, non-root execution, and a reverse proxy as the HTTP security
boundary.
