# ADR-0009: No Authentication in v1; TLS Is a Deployment Concern

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

`02` §21 says "Local-first · Optional authentication." `12` §3 says secure by default,
§7 wants authorization "enforced consistently across all interfaces", §15 wants secure
defaults. `08` §3 says "Use HTTPS exclusively."

Charter §12 ranks the PRD above architecture documents, so "optional authentication"
formally wins. And "HTTPS exclusively" is unlivable for a local-first tool: it means
self-signed certificates and browser warnings before anyone sees a dashboard.

## Decision

**No authentication in v1.** The local user is trusted. No credential store, no token
issuance, no login.

**HTTP is a first-class deployment.** Uvicorn speaks plain HTTP; TLS, when wanted, is
terminated by Caddy, Traefik or nginx in front. The application never manages
certificates. `08` §3's "HTTPS exclusively" is **superseded**: TLS is an optional
deployment concern, not an application requirement.

**Read-only mode is server-wide configuration**, not a per-identity permission — there
are no identities to attach it to. It is evaluated at a single enforcement point so a
later multi-user ADR can introduce identities without moving it. This is `12` §7's
"consistently across all interfaces" preserved as a seam rather than as RBAC.

**The DICOM plane has no authentication and cannot.** DIMSE offers only calling AE
title and source IP, both trivially spoofed. More importantly, default-deny is the
*wrong* default for this product: an association Probe rejects is an association Probe
cannot show you. So all associations are accepted by default, every one is audit-logged
with calling AE and source IP per `12` §10, an optional AE/IP allowlist ships, and the
DICOM port binds a configurable interface. A documented deviation from `12` §3 on the
DICOM plane only.

**Local-first is a tested property, not a claim.** `02` §21 promises no outbound
telemetry: no analytics, no update checks, no CDN fetches. Cornerstone3D, Tabulator,
HTMX, Alpine.js and Chart.js are therefore vendored locally (ADR-0025) — otherwise the
UI phones out on every page load and breaks in the air-gapped hospital networks these
users work in.

## Alternatives Considered

- **Mandatory auth with a first-run token.** Rejected: taxes the single-user localhost
  case, which is the overwhelmingly common one, against no threat it mitigates here.
- **Auth requirement coupled to network exposure.** Superseded by ADR-0010, which keeps
  the exposure gate without introducing credentials.

## Risks

- An unauthenticated service holding PHI. Bounded by ADR-0010's loopback default and
  exposure acknowledgment, and by ADR-0021's prohibition on plugin installation over
  the API.

## References

`02` §21 · `08` §3 · `12` §3, §7, §10, §15
